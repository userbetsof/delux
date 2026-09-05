"""Сравнение теневых БД Excel vs Python за день."""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEFAULT_EXCEL_DB = ROOT / "data" / "parity_excel.db"
DEFAULT_PYTHON_DB = ROOT / "data" / "parity_python.db"


def _norm_pred(val: Any) -> str:
    s = str(val or "").strip()
    if s in ("-", "—", "None", "none"):
        return ""
    return s


def _float_close(a: Any, b: Any, tol: float = 0.01) -> bool:
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return _norm_pred(a) == _norm_pred(b)


def _connect(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise FileNotFoundError(f"БД не найдена: {path}")
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _match_ids_for_date(conn: sqlite3.Connection, day: str) -> List[str]:
    # match_date в разных форматах: YYYY.MM.DD / YYYY-MM-DD / с временем
    day_dot = day.replace("-", ".")
    day_dash = day.replace(".", "-")
    cur = conn.execute(
        """
        SELECT match_id FROM matches
        WHERE match_date LIKE ? OR match_date LIKE ? OR match_date LIKE ? OR match_date LIKE ?
        ORDER BY match_id
        """,
        (f"{day_dot}%", f"{day_dash}%", f"{day_dot} %", f"{day_dash} %"),
    )
    return [r[0] for r in cur.fetchall()]


def _load_match_bundle(conn: sqlite3.Connection, match_id: str) -> Dict[str, Any]:
    m = conn.execute(
        "SELECT match_id, match_date, prediction, sport FROM matches WHERE match_id = ?",
        (match_id,),
    ).fetchone()
    if not m:
        return {}
    preds = {1: "", 2: "", 3: ""}
    for row in conn.execute(
        "SELECT strategy_id, prediction FROM strategy_predictions WHERE match_id = ?",
        (match_id,),
    ):
        preds[int(row["strategy_id"])] = row["prediction"] or ""
    # fallback: matches.prediction → NTB
    if not preds[1] and m["prediction"]:
        preds[1] = m["prediction"]

    outcomes: List[Dict[str, float]] = []
    rows = conn.execute(
        """
        SELECT strategy_id, home_win_prob, draw_prob, away_win_prob
        FROM outcome_probabilities
        WHERE match_id = ?
        ORDER BY strategy_id
        """,
        (match_id,),
    ).fetchall()
    for row in rows:
        # в БД хранится *100
        outcomes.append(
            {
                "strategy_idx": int(row["strategy_id"]) - 1,
                "home_prob": float(row["home_win_prob"] or 0) / 100.0,
                "draw_prob": float(row["draw_prob"] or 0) / 100.0,
                "away_prob": float(row["away_win_prob"] or 0) / 100.0,
            }
        )
    return {
        "match_id": match_id,
        "match_date": m["match_date"],
        "sport": m["sport"],
        "prediction_ntb": preds[1],
        "prediction_betalone": preds[2],
        "prediction_sniper": preds[3],
        "outcome_probabilities": outcomes,
    }


def compare_match_bundles(
    excel: Dict[str, Any],
    python: Dict[str, Any],
    *,
    strategy_tol: float = 0.01,
) -> List[str]:
    diffs: List[str] = []
    if not excel:
        diffs.append("missing_in_excel")
        return diffs
    if not python:
        diffs.append("missing_in_python")
        return diffs
    for key in ("prediction_ntb", "prediction_betalone", "prediction_sniper"):
        ev = _norm_pred(excel.get(key))
        pv = _norm_pred(python.get(key))
        if ev != pv:
            diffs.append(f"{key}: excel={excel.get(key)!r} python={python.get(key)!r}")

    eo = excel.get("outcome_probabilities") or []
    po = python.get("outcome_probabilities") or []
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


def compare_parity_dbs(
    excel_db: Path,
    python_db: Path,
    *,
    day: str,
    strategy_tol: float = 0.01,
) -> Dict[str, Any]:
    with _connect(excel_db) as ex, _connect(python_db) as py:
        ids_ex = set(_match_ids_for_date(ex, day))
        ids_py = set(_match_ids_for_date(py, day))
        all_ids = sorted(ids_ex | ids_py)

        reports = []
        ok_count = 0
        for mid in all_ids:
            eb = _load_match_bundle(ex, mid) if mid in ids_ex else {}
            pb = _load_match_bundle(py, mid) if mid in ids_py else {}
            diffs = compare_match_bundles(eb, pb, strategy_tol=strategy_tol)
            ok = len(diffs) == 0
            if ok:
                ok_count += 1
            reports.append(
                {
                    "match_id": mid,
                    "ok": ok,
                    "diff_count": len(diffs),
                    "diffs": diffs,
                    "excel": {
                        "prediction_ntb": eb.get("prediction_ntb"),
                        "prediction_betalone": eb.get("prediction_betalone"),
                        "prediction_sniper": eb.get("prediction_sniper"),
                    }
                    if eb
                    else None,
                    "python": {
                        "prediction_ntb": pb.get("prediction_ntb"),
                        "prediction_betalone": pb.get("prediction_betalone"),
                        "prediction_sniper": pb.get("prediction_sniper"),
                    }
                    if pb
                    else None,
                }
            )

    total = len(reports)
    pct = 100.0 * ok_count / total if total else 0.0
    return {
        "date": day,
        "excel_db": str(excel_db),
        "python_db": str(python_db),
        "total": total,
        "ok": ok_count,
        "pct": pct,
        "strategy_tol": strategy_tol,
        "reports": reports,
    }


def _resolve_day(raw: str) -> str:
    s = (raw or "today").strip().lower()
    if s in ("today", "сегодня", ""):
        return date.today().strftime("%Y.%m.%d")
    s = s.replace("-", ".")
    return s


def main() -> int:
    parser = argparse.ArgumentParser(description="Сравнение parity_excel.db vs parity_python.db")
    parser.add_argument("--excel-db", default=str(DEFAULT_EXCEL_DB))
    parser.add_argument("--python-db", default=str(DEFAULT_PYTHON_DB))
    parser.add_argument("--date", default="today", help="YYYY.MM.DD или today")
    parser.add_argument("--tol", type=float, default=0.01)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    day = _resolve_day(args.date)
    summary = compare_parity_dbs(
        Path(args.excel_db),
        Path(args.python_db),
        day=day,
        strategy_tol=args.tol,
    )
    out = Path(args.output) if args.output else ROOT / "data" / f"parity_daily_{day.replace('.', '-')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[+] Parity DB {day}: {summary['ok']}/{summary['total']} ({summary['pct']:.1f}%)")
    print(f"[+] Report: {out}")
    for rep in summary["reports"]:
        if rep["ok"]:
            continue
        print(f"  FAIL {rep['match_id']} ({rep['diff_count']})")
        for d in (rep.get("diffs") or [])[:8]:
            print(f"    - {d}")

    return 0 if summary["total"] > 0 and summary["ok"] == summary["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
