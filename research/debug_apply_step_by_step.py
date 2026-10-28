"""Debug apply_payload_to_store step by step."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from formula_port.workbook_loader import load_sheet_formulas, load_sheet_constants
from formula_port.cell_store import CellStore
from formula_port.team_stats import apply_payload_to_store, apply_settings_to_store, _table_rows, _find_team_in_table, _team_rates, _col
from analysis_data import load_analysis_data, build_settings
from match_store import get_queued_match
from settings import DeluxSettings
from sheets_config import DYNAMIC_SHEETS, SHEET_TABLE
import sqlite3

# Get match
con = sqlite3.connect('matches.db')
con.row_factory = sqlite3.Row
row = con.execute('SELECT match_id, sport FROM match_queue LIMIT 1').fetchone()
con.close()

queued = get_queued_match(row['match_id'])
match = queued.to_match_info()

cfg = DeluxSettings.from_env()
ms = build_settings(sport=queued.sport, source=cfg.source, tz_base=cfg.tz_base, dayzone_base=cfg.dayzone_base, time_offset=cfg.time_offset)

payload = load_analysis_data(match, ms)

print(f"Match: {match.home} vs {match.away}")

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

# Simulate apply_payload_to_store logic
overall_rows = _table_rows(payload.table_overall)
home_rows = _table_rows(payload.table_home)
away_rows = _table_rows(payload.table_away)

print(f"\noverall_rows: {len(overall_rows)} rows")
print(f"home_rows: {len(home_rows)} rows")
print(f"away_rows: {len(away_rows)} rows")

# M26-M28
print(f"\n=== M26-M28 ===")
if home_rows:
    home_team_row = _find_team_in_table(home_rows, match.home)
    print(f"home_team_row: {home_team_row}")
    if home_team_row:
        rates = _team_rates(home_team_row)
        print(f"rates: {rates}")
        if rates:
            for row_num, rate in zip((26, 27, 28), rates):
                addr = f"{_col(13)}{row_num}"
                store.set_value(SHEET_TABLE, addr, rate)
                print(f"  Set {addr} = {rate}")
        else:
            print("  rates is None!")
    else:
        print("  home_team_row is None!")
else:
    print("  home_rows is empty!")

# M30-M32
print(f"\n=== M30-M32 ===")
if away_rows:
    away_team_row = _find_team_in_table(away_rows, match.away)
    print(f"away_team_row: {away_team_row}")
    if away_team_row:
        rates = _team_rates(away_team_row)
        print(f"rates: {rates}")
        if rates:
            for row_num, rate in zip((30, 31, 32), rates):
                addr = f"{_col(3)}{row_num}"
                store.set_value(SHEET_TABLE, addr, rate)
                print(f"  Set {addr} = {rate}")
        else:
            print("  rates is None!")
    else:
        print("  away_team_row is None!")
else:
    print("  away_rows is empty!")

# Check results
print(f"\n=== Results ===")
print(f"M26 = {store.get(SHEET_TABLE, 'M26')}")
print(f"M27 = {store.get(SHEET_TABLE, 'M27')}")
print(f"M28 = {store.get(SHEET_TABLE, 'M28')}")
print(f"C30 = {store.get(SHEET_TABLE, 'C30')}")
print(f"C31 = {store.get(SHEET_TABLE, 'C31')}")
print(f"C32 = {store.get(SHEET_TABLE, 'C32')}")
print(f"M30 = {store.get(SHEET_TABLE, 'M30')}")
print(f"M31 = {store.get(SHEET_TABLE, 'M31')}")
print(f"M32 = {store.get(SHEET_TABLE, 'M32')}")
