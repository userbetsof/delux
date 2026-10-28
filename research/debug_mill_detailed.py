"""Debug Mill strategy for match 0tmcCQVh."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from formula_port.workbook_loader import load_sheet_formulas, load_sheet_constants
from formula_port.cell_store import CellStore
from formula_port.team_stats import apply_payload_to_store, apply_settings_to_store, apply_odds_to_store, apply_queued_odds
from formula_port.engine import evaluate_dynamic_sheets
from analysis_data import load_analysis_data
from odds_service import load_odds
from settings import DeluxSettings
from match_store import get_queued_match
from analysis_data import build_settings
from sheets_config import DYNAMIC_SHEETS

# Get match from queue
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
print(f"Payload: H2H={len(payload.h2h or [])}, Home={len(payload.home_all or [])}, Away={len(payload.away_all or [])}")

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

# Evaluate
evaluate_dynamic_sheets(store)

# Debug Mill key cells
print("\n=== Mill key cells ===")
for addr in ['P24', 'P36', 'R25', 'R27', 'R32', 'R37', 'R39', 'R44', 'T25', 'S49', 'W37', 'X39', 'Y37']:
    val = store.get('Mill', addr)
    formula = store.get_formula('Mill', addr)
    print(f"  Mill!{addr} = {val!r} (formula: {formula!r})")

# Debug Table sheet for P46:Q78 (VLOOKUP source)
print("\n=== Table sheet P46:Q55 ===")
for r in range(46, 56):
    p = store.get('Таблица', f'P{r}')
    q = store.get('Таблица', f'Q{r}')
    print(f"  P{r}={p!r} Q{r}={q!r}")

# Debug Incognito DATA
print("\n=== Incognito DATA key cells ===")
for addr in ['A1', 'A7', 'I2', 'I3', 'I4', 'I5', 'I8', 'I11', 'S6', 'T6', 'U6', 'W6', 'X6', 'Y6', 'H96', 'I96', 'J96', 'C44', 'C47', 'D44']:
    val = store.get('Incognito DATA', addr)
    print(f"  Incognito DATA!{addr} = {val!r}")

# Debug Analysis sheet
print("\n=== Analysis sheet strategy cells ===")
for addr in ['H8','J8','K8','H10','J10','K10','H16','J16','K16','H18','J18','K18','H20','J20','K20','H22','J22','K22','H24','J24','K24','H26','J26','K26']:
    val = store.get('Анализ', addr)
    print(f"  Анализ!{addr} = {val!r}")

print("\n=== Done ===")
