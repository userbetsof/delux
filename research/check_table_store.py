"""Check what Table sheet has in CellStore."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from formula_port.workbook_loader import load_sheet_formulas, load_sheet_constants
from formula_port.cell_store import CellStore
from formula_port.team_stats import apply_payload_to_store, apply_settings_to_store
from formula_port.engine import evaluate_dynamic_sheets
from analysis_data import load_analysis_data
from odds_service import load_odds
from settings import DeluxSettings
from match_store import get_queued_match
from analysis_data import build_settings
from sheets_config import DYNAMIC_SHEETS

# Get match
import sqlite3
con = sqlite3.connect('matches.db')
con.row_factory = sqlite3.Row
row = con.execute('SELECT match_id, sport FROM match_queue LIMIT 1').fetchone()
con.close()

queued = get_queued_match(row['match_id'])
match = queued.to_match_info()

cfg = DeluxSettings.from_env()
ms = build_settings(sport=queued.sport, source=cfg.source, tz_base=cfg.tz_base, dayzone_base=cfg.dayzone_base, time_offset=cfg.time_offset)

code, odds_data = load_odds(row['match_id'], cfg.source)
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

# Check Table sheet
print("=== Table sheet after apply_payload_to_store ===")
print(f"used_rows: {store.used_rows('Таблица')}")

# Check columns A-Z for row 1 (headers)
print("\nTable row 1 (headers):")
for c in range(1, 27):
    from openpyxl.utils import get_column_letter
    val = store.get('Таблица', f'{get_column_letter(c)}1')
    print(f"  {get_column_letter(c)}1 = {val!r}")

# Check columns A-I for rows 2-15 (data)
print("\nTable rows 2-5 (data):")
for r in range(2, 6):
    vals = [store.get('Таблица', f'{get_column_letter(c)}{r}') for c in range(1, 10)]
    print(f"  Row {r}: {vals}")

# Check columns M26-M32
print("\nTable M26-M32:")
for r in [26, 27, 28, 30, 31, 32]:
    val = store.get('Таблица', f'M{r}')
    formula = store.get_formula('Таблица', f'M{r}')
    print(f"  M{r} = {val!r} (formula: {formula!r})")

# Check columns AO42:AO69
print("\nTable AO cells (42-50):")
for r in range(42, 51):
    val = store.get('Таблица', f'AO{r}')
    formula = store.get_formula('Таблица', f'AO{r}')
    if val or formula:
        print(f"  AO{r} = {val!r} (formula: {formula!r})")

print("\n=== Done ===")
