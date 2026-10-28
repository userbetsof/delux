"""Дамп входов формулы X24 (Анализ!V16,Z16,X16,V19) и окружения."""

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


def show(sheet, addr):
    f = store._formulas.get(store.key(sheet, addr))
    v = store.get(sheet, addr)
    print(f"{sheet}!{addr:6} = {v!r}")
    if f:
        print(f"      {f}")


for addr in ("V16", "Z16", "X16", "V19", "P16", "Q16", "R16", "S16", "T16", "U16"):
    show(SHEET_ANALYSIS, addr)
print("--- Расчеты X116/Z116")
show(SHEET_CALC, "X116")
show(SHEET_CALC, "Z116")
print("--- BD39")
show("Графики", "BD39")
print("--- Mill C75")
show("Mill", "C75")
