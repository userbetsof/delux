"""Debug strategy 0 specifically."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from formula_port.workbook_loader import has_formula_cache, load_sheet_formulas, load_sheet_constants
from formula_port.cell_store import CellStore
from formula_port.team_stats import (
    apply_payload_to_store, apply_settings_to_store, apply_odds_to_store, apply_queued_odds
)
from formula_port.formula_evaluator import Evaluator, topological_sort
from formula_port.analiz import extract_results
from analysis_data import load_analysis_data
from odds_service import load_odds
from settings import DeluxSettings
from match_store import get_queued_match
from analysis_data import build_settings
from sheets_config import DYNAMIC_SHEETS, SHEET_CALC

# Get a match from queue
import sqlite3
con = sqlite3.connect('matches.db')
con.row_factory = sqlite3.Row
row = con.execute('SELECT match_id, sport FROM match_queue LIMIT 1').fetchone()
con.close()

match_id = row['match_id']
sport = row['sport']
print(f"Match: {match_id} (sport={sport})")

queued = get_queued_match(match_id)
match = queued.to_match_info()

cfg = DeluxSettings.from_env()
ms = build_settings(sport=queued.sport, source=cfg.source, tz_base=cfg.tz_base, dayzone_base=cfg.dayzone_base, time_offset=cfg.time_offset)

code, odds_data = load_odds(match_id, cfg.source)
if code != 0 or odds_data is None:
    odds_data = None

payload = load_analysis_data(match, ms)

# Build store
store = CellStore()
formulas = load_sheet_formulas("", list(DYNAMIC_SHEETS))
for sheet, mapping in formulas.items():
    store.bulk_set_formulas(sheet, mapping)

constants = load_sheet_constants("", list(formulas.keys()))
formula_keys = set(store._formulas)
for sheet, mapping in constants.items():
    for addr, val in mapping.items():
        key = store.key(sheet, addr)
        if key in formula_keys:
            continue
        store.set_value(sheet, addr, val)

apply_payload_to_store(store, payload)
apply_settings_to_store(store, ms.sport, ms.source)
if odds_data:
    apply_odds_to_store(store, odds_data)
apply_queued_odds(store, None)

# Evaluate dynamic sheets
from formula_port.engine import evaluate_dynamic_sheets
evaluate_dynamic_sheets(store)

# Check Incognito DATA values
print("\nIncognito DATA key cells:")
for addr in ['A1', 'I2', 'S6', 'T6', 'U6', 'T32', 'T34', 'W31', 'G16', 'L16']:
    val = store.get('Incognito DATA', addr)
    print(f"  {addr} = {val!r}")

# Check T16/T21/T28 chain
print("\nT16/T21/T28 chain:")
for addr in ['T16', 'T21', 'T28', 'P16', 'P20', 'P24', 'P28', 'G20', 'G24', 'G28']:
    val = store.get('Incognito DATA', addr)
    print(f"  {addr} = {val!r}")

# Check B3/B4/B5/C3/C4/C5 (for G20=G24=G28)
print("\nB3/B4/B5/C3/C4/C5 (for G20=C3/B3 etc.):")
for addr in ['B3', 'B4', 'B5', 'C3', 'C4', 'C5', 'I3', 'I4', 'I5']:
    val = store.get('Incognito DATA', addr)
    formula = store.get_formula('Incognito DATA', addr)
    print(f"  {addr} = {val!r} (formula: {formula!r})")

# Check Analysis sheet
print("\nAnalysis sheet key cells:")
for addr in ['H8', 'I8', 'J8', 'J9', 'K8', 'L8']:
    val = store.get('Анализ', addr)
    print(f"  {addr} = {val!r}")

# Extract results
results = extract_results(store, sport=ms.sport, skip_eval=True)
print("\nOutcome probabilities (first 3):")
for op in results.get("outcome_probabilities", [])[:3]:
    print(f"  strat {op['strategy_idx']}: H={op['home_prob']:.4f} D={op['draw_prob']:.4f} A={op['away_prob']:.4f}")

print("\n=== Done ===")
