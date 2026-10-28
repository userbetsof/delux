"""Debug apply_payload_to_store for match 4EFr4JFd."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from formula_port.workbook_loader import load_sheet_formulas, load_sheet_constants
from formula_port.cell_store import CellStore
from formula_port.team_stats import apply_payload_to_store, apply_settings_to_store, _table_rows
from analysis_data import load_analysis_data, build_settings
from odds_service import load_odds
from settings import DeluxSettings
from match_store import get_queued_match
from sheets_config import DYNAMIC_SHEETS, SHEET_TABLE
import sqlite3

# Get match 4EFr4JFd
con = sqlite3.connect('matches.db')
con.row_factory = sqlite3.Row
row = con.execute('SELECT match_id, sport FROM match_queue WHERE match_id="4EFr4JFd" LIMIT 1').fetchone()
con.close()

queued = get_queued_match(row['match_id'])
match = queued.to_match_info()

cfg = DeluxSettings.from_env()
ms = build_settings(sport=queued.sport, source=cfg.source, tz_base=cfg.tz_base, dayzone_base=cfg.dayzone_base, time_offset=cfg.time_offset)

code, odds_data = load_odds(row['match_id'], cfg.source)
if code != 0 or odds_data is None:
    odds_data = None

payload = load_analysis_data(match, ms)

print(f"Match: {match.home} vs {match.away}")
print(f"table_overall: {len(payload.table_overall or [])} rows")
print(f"table_home: {len(payload.table_home or [])} rows")

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

# Check before apply
print(f"\n=== Before apply_payload_to_store ===")
print(f"M26 = {store.get(SHEET_TABLE, 'M26')}")
print(f"M30 = {store.get(SHEET_TABLE, 'M30')}")

# Apply
apply_payload_to_store(store, payload)
apply_settings_to_store(store, ms.sport, ms.source)

# Check after apply
print(f"\n=== After apply_payload_to_store ===")
print(f"M26 = {store.get(SHEET_TABLE, 'M26')}")
print(f"M27 = {store.get(SHEET_TABLE, 'M27')}")
print(f"M28 = {store.get(SHEET_TABLE, 'M28')}")
print(f"M30 = {store.get(SHEET_TABLE, 'M30')}")
print(f"M31 = {store.get(SHEET_TABLE, 'M31')}")
print(f"M32 = {store.get(SHEET_TABLE, 'M32')}")

# Check C26-C32 (overall M column is C)
print(f"\n=== C26-C32 (overall M column) ===")
for r in [26, 27, 28, 30, 31, 32]:
    print(f"C{r} = {store.get(SHEET_TABLE, f'C{r}')}")
