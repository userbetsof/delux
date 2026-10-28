"""Debug Incognito DATA values from match_snapshot."""
import os, sys, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from formula_port.workbook_loader import load_sheet_formulas, load_sheet_constants
from formula_port.cell_store import CellStore
from formula_port.team_stats import apply_payload_to_store, apply_settings_to_store, _populate_incognito_data, _table_rows, _find_team_in_table
from sheets_config import DYNAMIC_SHEETS, SHEET_TABLE, SHEET_ANALYSIS
import sqlite3

# Get match 238n0PMk
con = sqlite3.connect('matches.db')
con.row_factory = sqlite3.Row
row = con.execute('SELECT match_id, sport FROM matches WHERE match_id="238n0PMk"').fetchone()

# Get team names
team_row = con.execute('SELECT t1.name as home, t2.name as away FROM matches m LEFT JOIN teams t1 ON m.home_team_id=t1.id LEFT JOIN teams t2 ON m.away_team_id=t2.id WHERE m.match_id="238n0PMk"').fetchone()
print(f"Match: {row['match_id']} | Home: {team_row['home']} | Away: {team_row['away']}")

# Get table_overall from match_snapshot
snapshot = con.execute('SELECT standings_json FROM match_snapshot WHERE match_id="238n0PMk"').fetchone()
con.close()

if not snapshot or not snapshot['standings_json']:
    print("No standings_json in match_snapshot!")
    sys.exit(1)

standings = json.loads(snapshot['standings_json'])
overall_data = standings.get('overall', [])
print(f"Overall rows: {len(overall_data)}")

# Convert to TableRow-like objects
class TableRow:
    def __init__(self, d):
        self.rank = d.get('rank', '')
        self.team = d.get('team', '')
        self.played = d.get('played', '')
        self.wins = d.get('wins', '')
        self.draws = d.get('draws', '')
        self.losses = d.get('losses', '')
        self.scored = d.get('scored', '')
        self.conceded = d.get('conceded', '')
        self.points = d.get('points', '')

overall_rows_obj = [TableRow(d) for d in overall_data]

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

# Convert to list format
overall_rows = _table_rows(overall_rows_obj)
print(f"\nOverall rows (list format): {len(overall_rows)}")

# Check if teams are found in table_overall
home_row = _find_team_in_table(overall_rows, team_row['home'])
away_row = _find_team_in_table(overall_rows, team_row['away'])
print(f"Home row found: {home_row}")
print(f"Away row found: {away_row}")

# Call _populate_incognito_data
_populate_incognito_data(store, overall_rows, team_row['home'], team_row['away'])

# Check Incognito DATA values
print(f"\n=== Incognito DATA B2-D11 ===")
for row_num in [2, 3, 4, 5, 8, 9, 10, 11]:
    b_val = store.get("Incognito DATA", f"B{row_num}")
    c_val = store.get("Incognito DATA", f"C{row_num}")
    d_val = store.get("Incognito DATA", f"D{row_num}")
    print(f"  B{row_num}={b_val}  C{row_num}={c_val}  D{row_num}={d_val}")

# Check G16-G17
print(f"\n=== Incognito DATA G16-G17 ===")
g16 = store.get("Incognito DATA", "G16")
g17 = store.get("Incognito DATA", "G17")
print(f"  G16={g16}  G17={g17}")

# Check S6-T6-U6
print(f"\n=== Incognito DATA S6-T6-U6 ===")
s6 = store.get("Incognito DATA", "S6")
t6 = store.get("Incognito DATA", "T6")
u6 = store.get("Incognito DATA", "U6")
print(f"  S6={s6}  T6={t6}  U6={u6}")

# Check Analysis H8-J8-K8
print(f"\n=== Analysis H8-J8-K8 ===")
h8 = store.get(SHEET_ANALYSIS, "H8")
j8 = store.get(SHEET_ANALYSIS, "J8")
k8 = store.get(SHEET_ANALYSIS, "K8")
print(f"  H8={h8}  J8={j8}  K8={k8}")
