"""Ежедневный паритет: Excel и Python → две теневые БД → сравнение.

Очередь матчей читается из боевой matches.db.
Результаты пишутся в data/parity_excel.db и data/parity_python.db (без 1pr).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

os.environ.setdefault("DELUX_SKIP_ONEPR", "1")

from analysis_data import build_settings, load_analysis_data  # noqa: E402
from calc_engine import ExcelCalcEngine  # noqa: E402
from compare_parity_dbs import _resolve_day, compare_parity_dbs  # noqa: E402
from db import create_database, database_path, get_database_path  # noqa: E402
from excel_com import _com_hresult, _COM_BUSY_HRESULTS  # noqa: E402
from formula_port.engine import PythonCalcEngine  # noqa: E402
from match_analysis import save_analysis_to_db  # noqa: E402
from match_store import QueuedMatch, list_queued_matches  # noqa: E402
from odds_service import build_fallback_odds, load_odds  # noqa: E402
from settings import DeluxSettings  # noqa: E402

PARITY_EXCEL = ROOT / "data" / "parity_excel.db"
PARITY_PYTHON = ROOT / "data" / "parity_python.db"


def _list_odds(queued: QueuedMatch):
    if queued.current_home or queued.current_draw or queued.current_away:
        return queued.current_home, queued.current_draw, queued.current_away
    if queued.start_home or queued.start_draw or queued.start_away:
        return queued.start_home, queued.start_draw, queued.start_away
    return None


def _queue_for_day(cfg: DeluxSettings, day: str, limit: int = 0) -> List[QueuedMatch]:
    """Матчи за день из боевой очереди (избранные лиги)."""
    day_dot = day.replace("-", ".")
    day_dash = day.replace(".", "-")
    # list_queued не фильтрует по дате — берём все избранные и фильтруем
    queued = list_queued_matches(
        leagues_by_sport=cfg.leagues_by_sport,
        new_only=False,
        limit=0,
    )
    out: List[QueuedMatch] = []
    for q in queued:
        dm = (q.date_match or "").strip()
        if not (dm.startswith(day_dot) or dm.startswith(day_dash)):
            continue
        if not cfg.is_favorite_league(q.sport, q.tour_name):
            continue
        out.append(q)
    out.sort(key=lambda q: (q.date_match, q.match_id))
    if limit and len(out) > limit:
        out = out[:limit]
    return out


def _prepare_payload(queued: QueuedMatch, cfg: DeluxSettings):
    match = queued.to_match_info()
    settings = cfg.match_settings
    if queued.sport:
        settings = build_settings(
            sport=queued.sport,
            source=cfg.source,
            tz_base=cfg.tz_base,
            dayzone_base=cfg.dayzone_base,
            time_offset=cfg.time_offset,
        )
    code, odds = load_odds(match.match_id, settings.source)
    if code != 0 or odds is None:
        odds = build_fallback_odds(match.match_id)
        if odds is None:
            raise RuntimeError(f"odds unavailable code={code}")
        print(f"[!] {match.match_id}: fallback odds (код {code})")
    if odds.home_id:
        match.home_participant_id = odds.home_id
    if odds.away_id:
        match.away_participant_id = odds.away_id

    last_err = None
    payload = None
    for attempt in range(4):
        try:
            payload = load_analysis_data(match, settings)
            last_err = None
            break
        except Exception as exc:
            last_err = exc
            time.sleep(2 + attempt * 3)
    if payload is None:
        raise RuntimeError(str(last_err))
    if not match.league and payload.h2h:
        match.league = payload.h2h[0].tour_name
        payload.match.league = match.league
    if not match.home and payload.h2h:
        match.home = payload.h2h[0].home_name
        payload.match.home = match.home
    if not match.away and payload.h2h:
        match.away = payload.h2h[0].away_name
        payload.match.away = match.away
    payload.match = match
    return payload, odds, settings, match


def _is_excel_com_busy(exc: BaseException) -> bool:
    hr = _com_hresult(exc)
    return hr is not None and hr in _COM_BUSY_HRESULTS


def _open_excel_engine(workbook: str, *, fresh: bool = False) -> ExcelCalcEngine:
    eng = ExcelCalcEngine(workbook, fresh=fresh)
    eng.__enter__()
    return eng


def _close_excel_engine(eng: ExcelCalcEngine | None) -> None:
    if eng is None:
        return
    try:
        eng.__exit__(None, None, None)
    except Exception:
        pass


def _run_excel_with_reconnect(
    eng: ExcelCalcEngine | None,
    workbook: str,
    payload,
    odds,
    *,
    list_odds,
) -> tuple[ExcelCalcEngine, Dict[str, Any]]:
    last_exc: Exception | None = None
    for attempt in range(2):
        if eng is None:
            eng = _open_excel_engine(workbook, fresh=attempt > 0)
        try:
            result = eng.run(payload, odds, list_odds=list_odds)
            return eng, result
        except Exception as exc:
            last_exc = exc
            if attempt == 0 and _is_excel_com_busy(exc):
                print("    [!] Excel busy — переподключение…")
                _close_excel_engine(eng)
                eng = None
                time.sleep(1.5)
                continue
            raise
    assert last_exc is not None
    raise last_exc


def _save_to_parity_db(db_file: Path, match_id: str, sport: int, results: Dict[str, Any], odds) -> None:
    os.environ["DELUX_SKIP_ONEPR"] = "1"
    create_database(str(db_file))
    with database_path(str(db_file)):
        save_analysis_to_db(
            match_id,
            sport,
            results,
            odds_markets=odds.all_markets_flat() if odds else None,
        )


def run_daily_parity(
    *,
    day: str,
    limit: int = 0,
    workbook: str = "",
    excel_db: Optional[Path] = None,
    python_db: Optional[Path] = None,
) -> Dict[str, Any]:
    cfg = DeluxSettings.from_env()
    # Боевая БД для очереди — не parity_*
    prod = get_database_path()
    if "parity_" in Path(prod).name.lower():
        os.environ["DATABASE_PATH"] = str(ROOT / "matches.db")

    day = _resolve_day(day)
    excel_db = Path(excel_db or PARITY_EXCEL)
    python_db = Path(python_db or PARITY_PYTHON)
    excel_db.parent.mkdir(parents=True, exist_ok=True)
    create_database(str(excel_db))
    create_database(str(python_db))

    calc_workbook = workbook or cfg.resolve_calc_workbook()
    matches = _queue_for_day(cfg, day, limit=limit)
    print(f"[*] Date {day}: {len(matches)} matches from queue ({get_database_path()})")
    print(f"[*] Excel DB:  {excel_db}")
    print(f"[*] Python DB: {python_db}")
    print(f"[*] Workbook:  {calc_workbook}")

    if not matches:
        summary = {
            "date": day,
            "excel_db": str(excel_db),
            "python_db": str(python_db),
            "total": 0,
            "ok": 0,
            "pct": 0.0,
            "reports": [],
            "error": "no matches in queue for date",
        }
        out = ROOT / "data" / f"parity_daily_{day.replace('.', '-')}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[!] Нет матчей в очереди за {day}")
        print(f"[+] Report: {out}")
        return summary

    py_eng = PythonCalcEngine(calc_workbook, pure_eval=True)
    run_log: List[Dict[str, Any]] = []

    excel_eng: ExcelCalcEngine | None = None
    try:
        excel_eng = _open_excel_engine(calc_workbook, fresh=False)
        for idx, queued in enumerate(matches, 1):
            mid = queued.match_id
            print(f"\n[{idx}/{len(matches)}] {mid} | {queued.tour_name} | {queued.home_name} - {queued.away_name}")
            entry: Dict[str, Any] = {"match_id": mid, "excel_ok": False, "python_ok": False}
            try:
                payload, odds, settings, match = _prepare_payload(queued, cfg)
                list_odds = _list_odds(queued)

                excel_eng, ex = _run_excel_with_reconnect(
                    excel_eng,
                    calc_workbook,
                    payload,
                    odds,
                    list_odds=list_odds,
                )
                ex["match_id"] = mid
                ex["sport"] = settings.sport
                if not ex.get("match_date") and match.date:
                    ex["match_date"] = match.date
                if not ex.get("league") and match.league:
                    ex["league"] = match.league
                if not ex.get("home") and match.home:
                    ex["home"] = match.home
                if not ex.get("away") and match.away:
                    ex["away"] = match.away
                _save_to_parity_db(excel_db, mid, settings.sport, ex, odds)
                entry["excel_ok"] = True
                print(
                    f"    excel NTB={ex.get('prediction_ntb')!r} "
                    f"Betalone={ex.get('prediction_betalone')!r} "
                    f"Sniper={ex.get('prediction_sniper')!r}"
                )

                pr = py_eng.run(payload, odds, list_odds=list_odds)
                pr["match_id"] = mid
                pr["sport"] = settings.sport
                if not pr.get("match_date") and match.date:
                    pr["match_date"] = match.date
                if not pr.get("league") and match.league:
                    pr["league"] = match.league
                if not pr.get("home") and match.home:
                    pr["home"] = match.home
                if not pr.get("away") and match.away:
                    pr["away"] = match.away
                _save_to_parity_db(python_db, mid, settings.sport, pr, odds)
                entry["python_ok"] = True
                print(
                    f"    python NTB={pr.get('prediction_ntb')!r} "
                    f"Betalone={pr.get('prediction_betalone')!r} "
                    f"Sniper={pr.get('prediction_sniper')!r}"
                )
            except Exception as exc:
                entry["error"] = str(exc)
                print(f"    [-] {exc}")
            run_log.append(entry)
    finally:
        _close_excel_engine(excel_eng)

    summary = compare_parity_dbs(excel_db, python_db, day=day, strategy_tol=0.01)
    summary["run_log"] = run_log
    out = ROOT / "data" / f"parity_daily_{day.replace('.', '-')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[+] Parity: {summary['ok']}/{summary['total']} ({summary['pct']:.1f}%)")
    print(f"[+] Report: {out}")
    for rep in summary.get("reports") or []:
        if rep.get("ok"):
            continue
        print(f"  FAIL {rep['match_id']} ({rep.get('diff_count')})")
        for d in (rep.get("diffs") or [])[:6]:
            print(f"    - {d}")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Daily Excel vs Python parity into twin DBs")
    parser.add_argument("--date", default="today", help="YYYY.MM.DD или today")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--workbook", default="")
    parser.add_argument("--excel-db", default=str(PARITY_EXCEL))
    parser.add_argument("--python-db", default=str(PARITY_PYTHON))
    args = parser.parse_args()

    summary = run_daily_parity(
        day=args.date,
        limit=args.limit,
        workbook=args.workbook,
        excel_db=Path(args.excel_db),
        python_db=Path(args.python_db),
    )
    total = int(summary.get("total") or 0)
    ok = int(summary.get("ok") or 0)
    if total == 0:
        return 1
    return 0 if ok == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
