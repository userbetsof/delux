"""Полный прогон engine.run для проблемного матча + дамп ключевых ячеек."""

import sys
import traceback

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:\papki\work\bets\delux")

from analysis_data import MatchInfo, load_analysis_data
from settings import DeluxSettings
from match_analysis import _fetch_match_status
from odds_service import load_odds, build_fallback_odds
from calc_backend import get_calc_engine

MATCH = sys.argv[1] if len(sys.argv) > 1 else "25Xg8KYr"

cfg = DeluxSettings.from_env()
settings = cfg.match_settings

status = _fetch_match_status(MATCH, settings.sport)
match = MatchInfo(match_id=MATCH)
match.status = status
payload = load_analysis_data(match, settings)

code, odds_data = load_odds(MATCH, settings.source)
if code != 0 or odds_data is None:
    odds_data = build_fallback_odds(MATCH)
print("odds code:", code)

engine = get_calc_engine()
engine.__enter__()
try:
    results = engine.run(payload, odds_data, list_odds=None)
finally:
    engine.__exit__(None, None, None)

for k in ("prediction_ntb", "prediction_betalone", "prediction_sniper",
          "outcome_probabilities", "home_goals", "away_goals"):
    print(f"{k} = {results.get(k)!r}")

# ключевые ячейки, участвующие в прогнозах
store = getattr(engine, "store", None) or getattr(engine, "_store", None)
if store is None:
    print("store not found on engine:", [a for a in dir(engine) if "store" in a.lower()])
else:
    from sheets_config import SHEET_ANALYSIS, SHEET_CALC
    keys = [
        (SHEET_ANALYSIS, "S13"), (SHEET_ANALYSIS, "O10"), (SHEET_ANALYSIS, "X24"),
        (SHEET_ANALYSIS, "X25"), (SHEET_ANALYSIS, "O11"), (SHEET_ANALYSIS, "S14"),
        (SHEET_CALC, "Z112"), (SHEET_ANALYSIS, "AE24"), (SHEET_ANALYSIS, "AE23"),
    ]
    for sheet, addr in keys:
        print(f"  {sheet}!{addr} = {store.get(sheet, addr)!r}")
