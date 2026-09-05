"""Дамп ключевых ячеек Графики / Analysis после pure_eval."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analysis_data import build_settings, load_analysis_data
from formula_port.engine import PythonCalcEngine, evaluate_dynamic_sheets
from match_store import get_queued_match
from odds_service import load_odds
from settings import DeluxSettings

MID = sys.argv[1] if len(sys.argv) > 1 else "4USqzNnI"
GRAF = "Графики"
AN = "Анализ"


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
    store = PythonCalcEngine(cfg.resolve_calc_workbook(), pure_eval=True)._build_store(payload, odds)
    evaluate_dynamic_sheets(store)

    print("=== Графики ===")
    for a in [
        "BC22", "BD36", "BD37", "BD38", "BD39",
        "M26", "M27", "M28", "M30", "M31", "M32",
        "N30", "O30", "AO42", "AO43",
    ]:
        print(f"{a}\t{store.get(GRAF, a)!r}\t{store.get_formula(GRAF, a)}")

    print("=== Анализ sniper inputs ===")
    for a in ["H26", "J26", "K26", "V16", "X16", "Z16", "AE24", "V19", "O10", "X24", "S13"]:
        print(f"{a}\t{store.get(AN, a)!r}\t{store.get_formula(AN, a)}")

    # strategies summary
    print("=== strategies ===")
    for i in range(10):
        row = 8 + i * 2
        print(
            f"[{i}] H={store.get(AN, f'H{row}')!r} J={store.get(AN, f'J{row}')!r} "
            f"K={store.get(AN, f'K{row}')!r}"
        )


if __name__ == "__main__":
    main()
