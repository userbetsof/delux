"""Сравнение входов Incognito (A1/I2/B2) и листа коэффициентов."""
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
from sheets_config import SHEET_CALC, SHEET_ODDS

MID = sys.argv[1] if len(sys.argv) > 1 else "G8d2h42n"


def main() -> None:
    cfg = DeluxSettings.from_env()
    q = get_queued_match(MID)
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
        inc = eng.wb.Worksheets("Incognito DATA")
        odd = eng.wb.Worksheets("Коэффициенты")
        calc = eng.wb.Worksheets("Расчеты")
        print("XL Calc A1", calc.Range("A1").Value)
        print("XL Inc A1", inc.Range("A1").Value, "f", inc.Range("A1").Formula)
        print("XL Inc I2", inc.Range("I2").Value, "f", inc.Range("I2").Formula)
        for a in ("B2", "C2", "D2", "B3", "C3", "G16", "G20"):
            print(f"XL Inc {a}", inc.Range(a).Value)
        print("XL Odds A1:B2", odd.Range("A1").Value, odd.Range("B1").Value, odd.Range("A2").Value, odd.Range("B2").Value)
        print("XL Odds C1:E5")
        for r in range(1, 8):
            print(" ", r, [odd.Cells(r, c).Value for c in range(1, 8)])

    py = PythonCalcEngine(wb, pure_eval=True)
    store = py._build_store(payload, odds)
    evaluate_dynamic_sheets(store)
    print("PY Calc A1", store.get(SHEET_CALC, "A1"))
    print("PY Inc A1", store.get("Incognito DATA", "A1"), store.get_formula("Incognito DATA", "A1"))
    print("PY Inc I2", store.get("Incognito DATA", "I2"), store.get_formula("Incognito DATA", "I2"))
    for a in ("B2", "C2", "D2", "B3", "C3", "G16", "G20", "P20", "P28"):
        print(f"PY Inc {a}", store.get("Incognito DATA", a), store.get_formula("Incognito DATA", a))
    print("PY Odds A1:B2", store.get(SHEET_ODDS, "A1"), store.get(SHEET_ODDS, "B1"), store.get(SHEET_ODDS, "A2"), store.get(SHEET_ODDS, "B2"))
    print("PY Odds C3:E6")
    for r in range(1, 8):
        print(" ", r, [store.get(SHEET_ODDS, f"{chr(64+c)}{r}") for c in range(1, 8)])


if __name__ == "__main__":
    main()
