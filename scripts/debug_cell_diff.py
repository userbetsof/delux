"""Сравнить ключевые ячейки Excel vs Python для одного матча (быстро)."""
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

MID = sys.argv[1] if len(sys.argv) > 1 else "4USqzNnI"

CELLS = {
    "Incognito DATA": [
        "G16", "G20", "G24", "G28", "W13", "X13", "Y13", "Z11", "Z12",
        "W6", "X6", "Y6", "C44", "C47", "D44", "H96", "I96", "J96",
    ],
    "Mill": ["W37", "X39", "Y37", "X26", "S49"],
    "Графики": [
        "BC20", "BC21", "BC22", "BC24", "BC25", "BC26", "BC27",
        "BC34", "BD34", "BE34", "BC35", "BD35", "BE35",
        "BD36", "BD37", "BD38", "BD39",
        "AM42", "AN42", "AO42", "M26", "M27", "M28", "M30", "M31", "M32",
        "N30", "O30", "U26", "V26", "W26", "K28",
    ],
    "Elizabet2": ["W16", "W17", "W18"],
}


def main() -> None:
    cfg = DeluxSettings.from_env()
    q = get_queued_match(MID)
    assert q
    ms = build_settings(
        sport=q.sport,
        source=cfg.source,
        tz_base=cfg.tz_base,
        dayzone_base=cfg.dayzone_base,
        time_offset=cfg.time_offset,
    )
    match = q.to_match_info()
    _, odds = load_odds(MID, ms.source)
    if odds:
        if odds.home_id:
            match.home_participant_id = odds.home_id
        if odds.away_id:
            match.away_participant_id = odds.away_id
    payload = load_analysis_data(match, ms)
    wb = cfg.resolve_calc_workbook()

    xl_vals = {}
    with ExcelCalcEngine(wb, fresh=True) as eng:
        eng.run(payload, odds)
        for sheet, addrs in CELLS.items():
            ws = eng.wb.Worksheets(sheet)
            for a in addrs:
                xl_vals[(sheet, a)] = ws.Range(a).Value

    store = PythonCalcEngine(wb, pure_eval=True)._build_store(payload, odds)
    evaluate_dynamic_sheets(store)

    print(f"match {MID}")
    for sheet, addrs in CELLS.items():
        print(f"=== {sheet} ===")
        for a in addrs:
            xv = xl_vals.get((sheet, a))
            pv = store.get(sheet, a)
            mark = "OK" if str(xv) == str(pv) else "DIFF"
            if isinstance(xv, (int, float)) and isinstance(pv, (int, float)):
                mark = "OK" if abs(float(xv) - float(pv)) < 1e-6 else "DIFF"
            if mark == "DIFF":
                print(f"  {a}\tXL={xv!r}\tPY={pv!r}")


if __name__ == "__main__":
    main()
