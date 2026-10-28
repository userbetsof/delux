"""
5Match strategy: reads from Table sheet M26, M27, M28.
From formula_graph:
  Анализ!H26 = Таблица!M30
  Анализ!J26 = Таблица!M31  
  Анализ!K26 = Таблица!M32

M26/M27/M28/M30/M31/M32 are on Table sheet and are NOT in formula_graph.
They must be computed from table data.

From screenshot: 5Match = 17%/60%/23%
H26 = 17% = M30
J26 = 60% = M31
K26 = 23% = M32

These are likely win/draw/loss probabilities computed from team ratings.
"""
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
from sheets_config import DYNAMIC_SHEETS, SHEET_TABLE

# Get match
import sqlite3
con = sqlite3.connect('matches.db')
con.row_factory = sqlite3.Row
row = con.execute('SELECT match_id, sport FROM match_queue WHERE match_id="0tmcCQVh" LIMIT 1').fetchone()
if not row:
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
print(f"table_overall: {len(payload.table_overall or [])} rows")

# Check what's in table_overall for our teams
home_name = match.home
away_name = match.away
print(f"\nLooking for teams in table_overall:")
for r in payload.table_overall or []:
    team = r.team if hasattr(r, 'team') else r.get('team', '') if isinstance(r, dict) else str(r)
    if home_name in team or away_name in team:
        print(f"  Found: {team}")

# Check Table sheet in CellStore
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

# Check what's on Table sheet for home/away teams
print(f"\n=== Table sheet for our teams ===")
for r_idx, r in enumerate(payload.table_overall or []):
    team = r.team if hasattr(r, 'team') else r.get('team', '') if isinstance(r, dict) else str(r)
    if home_name in team or away_name in team:
        rank = r.rank if hasattr(r, 'rank') else r.get('rank', '')
        played = r.played if hasattr(r, 'played') else r.get('played', '')
        wins = r.wins if hasattr(r, 'wins') else r.get('wins', '')
        draws = r.draws if hasattr(r, 'draws') else r.get('draws', '')
        losses = r.losses if hasattr(r, 'losses') else r.get('losses', '')
        scored = r.scored if hasattr(r, 'scored') else r.get('scored', '')
        conceded = r.conceded if hasattr(r, 'conceded') else r.get('conceded', '')
        points = r.points if hasattr(r, 'points') else r.get('points', '')
        print(f"  {team}: rank={rank} P={played} W={wins} D={draws} L={losses} GF={scored} GA={conceded} Pts={points}")

print("\n=== Done ===")
