"""Сравнение ключевых ячеек Incognito DATA / стратегий Excel vs Python."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analysis_data import build_settings, load_analysis_data
from calc_engine import ExcelCalcEngine
from formula_port.engine import PythonCalcEngine, evaluate_dynamic_sheets
from match_store import get_queued_match
from odds_service import load_odds
from settings import DeluxSettings

MID = sys.argv[1] if len(sys.argv) > 1 else "G8d2h42n"
CELLS = [
    "S6", "T6", "U6", "W6", "X6", "Y6",
    "T32", "T34", "T16", "T21", "T28", "W31",
    "C44", "C47", "D44", "H96", "I96", "J96",
    "J13", "K13", "L13",
]


def main() -> None:
    cfg = DeluxSettings.from_env()
    q = get_queued_match(MID)
    assert q, MID
    ms = build_settings(
        sport=q.sport,
        source=cfg.source,
        tz_base=cfg.tz_base,
        dayzone_base=cfg.dayzone_base,
        time_offset=cfg.time_offset,
    )
    payload = load_analysis_data(q.to_match_info(), ms)
    _, odds = load_odds(MID, ms.source)
    wb = cfg.resolve_calc_workbook()

    with ExcelCalcEngine(wb, fresh=True) as eng:
        eng.run(payload, odds)
        ws = eng.wb.Worksheets("Incognito DATA")
        print("=== EXCEL Incognito DATA ===")
        for a in CELLS:
            print(f"XL {a}\t{ws.Range(a).Value!r}")

    py = PythonCalcEngine(wb, pure_eval=True)
    store = py._build_store(payload, odds)
    evaluate_dynamic_sheets(store)
    print("=== PYTHON Incognito DATA ===")
    for a in CELLS:
        print(f"PY {a}\t{store.get('Incognito DATA', a)!r}\t{store.get_formula('Incognito DATA', a)}")


if __name__ == "__main__":
    main()
