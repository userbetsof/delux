"""Сравнение Excel vs Python pure_eval (без COM в python-ветке)."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analysis_data import MatchInfo, build_settings, load_analysis_data  # noqa: E402
from calc_engine import ExcelCalcEngine  # noqa: E402
from db import create_database, get_db_connection  # noqa: E402
from formula_port.com_guard import com_call_count, reset_com_calls  # noqa: E402
from formula_port.engine import PythonCalcEngine  # noqa: E402
from match_store import QueuedMatch, get_queued_match, list_queued_matches  # noqa: E402
from odds_service import load_odds  # noqa: E402
from settings import DeluxSettings  # noqa: E402


def _norm_pred(val: Any) -> str:
    s = str(val or "").strip()
    if s in ("-", "—", "None"):
        return ""
    return s


def _float_close(a: Any, b: Any, tol: float = 0.01) -> bool:
    """Допуск 1 п.п. (0.01) для вероятностей стратегий."""
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return _norm_pred(a) == _norm_pred(b)


def _compare_results(excel_r: Dict, py_r: Dict, *, strategy_tol: float = 0.01) -> List[str]:
    """Успех: одинаковые прогнозы; 10 стратегий — отклонение ≤ strategy_tol (по умолч. 1%)."""
    diffs: List[str] = []
    for key in ("prediction_ntb", "prediction_betalone", "prediction_sniper"):
        ev = _norm_pred(excel_r.get(key))
        pv = _norm_pred(py_r.get(key))
        if ev != pv:
            diffs.append(f"{key}: excel={excel_r.get(key)!r} python={py_r.get(key)!r}")

    eo = excel_r.get("outcome_probabilities") or []
    po = py_r.get("outcome_probabilities") or []
    if len(eo) < 10 or len(po) < 10:
        diffs.append(f"strategies_count: excel={len(eo)} python={len(po)} (need 10)")
    for i in range(min(10, len(eo), len(po))):
        e, p = eo[i], po[i]
        for fld in ("home_prob", "draw_prob", "away_prob"):
            if not _float_close(e.get(fld), p.get(fld), strategy_tol):
                diffs.append(
                    f"strategy[{i}].{fld}: excel={e.get(fld)} python={p.get(fld)} "
                    f"(tol={strategy_tol})"
                )
    return diffs


def _list_odds(queued: QueuedMatch):
    if queued.current_home or queued.current_draw or queued.current_away:
        return queued.current_home, queued.current_draw, queued.current_away
    if queued.start_home or queued.start_draw or queued.start_away:
        return queued.start_home, queued.start_draw, queued.start_away
    return None


def validate_match(
    match_id: str,
    calc_workbook: str,
    cfg: DeluxSettings,
    *,
    excel_engine: ExcelCalcEngine = None,
    py_engine: PythonCalcEngine = None,
) -> Dict[str, Any]:
    queued = get_queued_match(match_id) or QueuedMatch(match_id=match_id, sport=cfg.sport)
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

    code, odds_data = load_odds(match.match_id, settings.source)
    if code != 0 or odds_data is None:
        return {"match_id": match_id, "ok": False, "error": f"odds code {code}"}
    if odds_data.home_id:
        match.home_participant_id = odds_data.home_id
    if odds_data.away_id:
        match.away_participant_id = odds_data.away_id

    last_err = None
    payload = None
    for attempt in range(4):
        try:
            payload = load_analysis_data(match, settings)
            last_err = None
            break
        except Exception as exc:
            last_err = exc
            time.sleep(3 + attempt * 4)
    if payload is None:
        return {"match_id": match_id, "ok": False, "error": str(last_err)}
    if not match.league and payload.h2h:
        match.league = payload.h2h[0].tour_name
        payload.match.league = match.league
    if not match.home and payload.h2h:
        match.home = payload.h2h[0].home_name
        payload.match.home = match.home
    if not match.away and payload.h2h:
        match.away = payload.h2h[0].away_name
        payload.match.away = match.away

    if odds_data.home_id:
        payload.match.home_participant_id = odds_data.home_id
    if odds_data.away_id:
        payload.match.away_participant_id = odds_data.away_id

    list_odds = _list_odds(queued)

    excel_results = excel_engine.run(payload, odds_data, list_odds=list_odds)

    reset_com_calls()
    py_results = py_engine.run(payload, odds_data, list_odds=list_odds)
    com_used = com_call_count()
    diffs = _compare_results(excel_results, py_results)
    if com_used:
        diffs.append(f"COM_USED={com_used} (pure_eval must not call Excel)")

    return {
        "match_id": match_id,
        "home": str(excel_results.get("home") or py_results.get("home") or ""),
        "away": str(excel_results.get("away") or py_results.get("away") or ""),
        "league": str(excel_results.get("league") or py_results.get("league") or ""),
        "ok": len(diffs) == 0,
        "com_calls": com_used,
        "diff_count": len(diffs),
        "diffs": diffs,
        "excel": {
            "prediction_ntb": excel_results.get("prediction_ntb"),
            "prediction_betalone": excel_results.get("prediction_betalone"),
            "prediction_sniper": excel_results.get("prediction_sniper"),
        },
        "python": {
            "prediction_ntb": py_results.get("prediction_ntb"),
            "prediction_betalone": py_results.get("prediction_betalone"),
            "prediction_sniper": py_results.get("prediction_sniper"),
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Excel vs Python formula parity (pure_eval)")
    parser.add_argument("--limit", type=int, default=0, help="0 = все выбранные матчи")
    parser.add_argument("--match-id", default="")
    parser.add_argument("--today", action="store_true", help="Матчи из очереди на сегодня")
    parser.add_argument("--date", default="", help="Дата очереди YYYY.MM.DD")
    parser.add_argument(
        "--sport",
        type=int,
        default=0,
        help="Фильтр вида спорта (1=футбол, 3=баскетбол, 4=хоккей, 6=бейсбол); 0=все",
    )
    parser.add_argument("--workbook", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--hybrid", action="store_true", help="PythonCalcEngine without pure_eval")
    args = parser.parse_args()

    cfg = DeluxSettings.from_env()
    workbook = args.workbook or cfg.resolve_calc_workbook()
    create_database()

    day = ""
    if args.today:
        day = date.today().strftime("%Y.%m.%d")
    elif args.date:
        day = args.date.strip()

    sport_filter = int(args.sport or 0)
    sport_aliases: list[int] = []
    if sport_filter:
        from settings import sport_id_aliases

        sport_aliases = list(sport_id_aliases(sport_filter))

    if args.match_id:
        match_ids = [args.match_id]
    elif day:
        prefix = day + "%"
        sql = "SELECT match_id FROM match_queue WHERE date_match LIKE ?"
        params: list = [prefix]
        if sport_aliases:
            placeholders = ",".join("?" * len(sport_aliases))
            sql += f" AND sport IN ({placeholders})"
            params.extend(sport_aliases)
        sql += " ORDER BY date_match, match_id"
        with get_db_connection() as conn:
            cur = conn.execute(sql, params)
            match_ids = [r[0] for r in cur.fetchall()]
        if args.limit and len(match_ids) > args.limit:
            match_ids = match_ids[: args.limit]
        sport_note = f" sport={sport_filter}" if sport_filter else ""
        print(f"[*] Date {day}{sport_note}: {len(match_ids)} matches")
    else:
        limit = args.limit or 20
        with get_db_connection() as conn:
            cur = conn.execute("SELECT match_id FROM matches WHERE match_id != '' LIMIT ?", (limit,))
            match_ids = [r[0] for r in cur.fetchall()]
        if not match_ids:
            queued = list_queued_matches(limit=limit)
            match_ids = [q.match_id for q in queued]

    if not match_ids:
        print("[-] No matches for validation")
        raise SystemExit(1)

    reports = []
    ok_count = 0
    pure = not args.hybrid
    py_eng = PythonCalcEngine(workbook, pure_eval=pure)
    print(f"[*] PythonCalcEngine pure_eval={pure}")
    with ExcelCalcEngine(workbook, fresh=True) as excel_eng:
        for mid in match_ids:
            print(f"[*] Validating {mid}...")
            try:
                rep = validate_match(mid, workbook, cfg, excel_engine=excel_eng, py_engine=py_eng)
            except Exception as exc:
                rep = {"match_id": mid, "ok": False, "error": str(exc)}
            reports.append(rep)
            if rep.get("ok"):
                ok_count += 1
                print(
                    f"    OK  {rep.get('home')} - {rep.get('away')} | "
                    f"NTB={rep['excel'].get('prediction_ntb')}"
                )
            else:
                ex = rep.get("excel") or {}
                py = rep.get("python") or {}
                print(
                    f"    FAIL {rep.get('home') or ''} - {rep.get('away') or ''} "
                    f"({rep.get('diff_count') or 'err'})"
                )
                if ex or py:
                    print(
                        f"      NTB excel={ex.get('prediction_ntb')!r} python={py.get('prediction_ntb')!r}"
                    )
                    print(
                        f"      Betalone excel={ex.get('prediction_betalone')!r} python={py.get('prediction_betalone')!r}"
                    )
                    print(
                        f"      Sniper excel={ex.get('prediction_sniper')!r} python={py.get('prediction_sniper')!r}"
                    )
                if rep.get("error"):
                    print(f"      error: {rep['error']}")

    pct = 100.0 * ok_count / len(reports) if reports else 0
    summary = {
        "total": len(reports),
        "ok": ok_count,
        "pct": pct,
        "pure_eval": pure,
        "reports": reports,
    }
    print(f"\n[+] Parity: {ok_count}/{len(reports)} ({pct:.1f}%)")

    out = args.output or str(ROOT / "data" / "parity_report.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"    report: {out}")

    raise SystemExit(0 if pct >= 95 or (len(reports) >= 1 and ok_count == len(reports)) else 1)


if __name__ == "__main__":
    main()
