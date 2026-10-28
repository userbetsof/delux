"""Почему X24 = #N/A: смотрим формулы/значения ключевых ячеек."""

import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:\papki\work\bets\delux")

from analysis_data import MatchInfo, load_analysis_data
from settings import DeluxSettings
from match_analysis import _fetch_match_status
from odds_service import load_odds, build_fallback_odds
from calc_backend import get_calc_engine
from formula_port.engine import evaluate_dynamic_sheets
from sheets_config import SHEET_ANALYSIS, SHEET_CALC

MATCH = sys.argv[1] if len(sys.argv) > 1 else "25Xg8KYr"

settings = DeluxSettings.from_env().match_settings
match = MatchInfo(match_id=MATCH)
match.status = _fetch_match_status(MATCH, settings.sport)
payload = load_analysis_data(match, settings)
code, odds_data = load_odds(MATCH, settings.source)
if code != 0 or odds_data is None:
    odds_data = build_fallback_odds(MATCH)

engine = get_calc_engine()
store = engine._build_store(payload, odds_data, None)
evaluate_dynamic_sheets(store)

targets = [
    (SHEET_ANALYSIS, "S12"), (SHEET_ANALYSIS, "S13"), (SHEET_ANALYSIS, "S14"),
    (SHEET_ANALYSIS, "O10"), (SHEET_ANALYSIS, "O9"), (SHEET_ANALYSIS, "O11"),
    (SHEET_ANALYSIS, "X23"), (SHEET_ANALYSIS, "X24"), (SHEET_ANALYSIS, "X25"),
    (SHEET_ANALYSIS, "AE23"), (SHEET_ANALYSIS, "AE24"),
    (SHEET_CALC, "Z112"), (SHEET_CALC, "Z113"),
]
for sheet, addr in targets:
    formula = store._formulas.get(store.key(sheet, addr))
    value = store.get(sheet, addr)
    print(f"{sheet}!{addr:5} = {value!r}")
    if formula:
        print(f"    formula: {formula}")
