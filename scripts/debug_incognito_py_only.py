"""Быстрый дамп Incognito без Excel COM — только Python pure_eval."""
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
CELLS = [
    "A1", "I2", "S6", "T6", "U6", "W6", "X6", "Y6",
    "T16", "T21", "T28", "T32", "T34", "W31",
    "C44", "C47", "D44", "H96", "I96", "J96",
    "J13", "K13", "L13",
]


def main() -> None:
    cfg = DeluxSettings.from_env()
    q = get_queued_match(MID)
    if not q:
        print("not queued", MID)
        return
    ms = build_settings(
        sport=q.sport,
        source=cfg.source,
        tz_base=cfg.tz_base,
        dayzone_base=cfg.dayzone_base,
        time_offset=cfg.time_offset,
    )
    match = q.to_match_info()
    code, odds = load_odds(MID, ms.source)
    print(f"odds code={code}")
    if odds and odds.home_id:
        match.home_participant_id = odds.home_id
    if odds and odds.away_id:
        match.away_participant_id = odds.away_id
    payload = load_analysis_data(match, ms)
    print(
        f"h2h={len(payload.h2h)} home_all={len(payload.home_all)} "
        f"away_all={len(payload.away_all)}"
    )
    print(f"teams {payload.match.home!r} - {payload.match.away!r}")
    wb = cfg.resolve_calc_workbook()
    py = PythonCalcEngine(wb, pure_eval=True)
    store = py._build_store(payload, odds)
    # quick check history sheets
    for sh in ("Очные", "Дома", "Гости", "Таблица"):
        rows = store.used_rows(sh)
        print(f"store {sh} used_rows={rows} sample A1={store.get(sh,'A1')!r} A2={store.get(sh,'A2')!r}")
    evaluate_dynamic_sheets(store)
    print("=== PYTHON Incognito DATA ===")
    for a in CELLS:
        print(f"PY {a}\t{store.get('Incognito DATA', a)!r}\t{store.get_formula('Incognito DATA', a)}")
    # Analysis strategy cells
    for a in ("H8", "J8", "K8", "O10", "X24", "S13"):
        print(f"AN {a}\t{store.get('Анализ', a)!r}\t{store.get_formula('Анализ', a)}")


if __name__ == "__main__":
    main()
