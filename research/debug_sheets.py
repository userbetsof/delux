"""Deep debug: check what's written to sheets by apply_payload_to_store."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from formula_port.cell_store import CellStore
from formula_port.workbook_loader import load_sheet_formulas, load_sheet_constants
from formula_port.team_stats import apply_payload_to_store, apply_settings_to_store, apply_odds_to_store, apply_queued_odds
from analysis_data import load_analysis_data
from match_store import get_queued_match
from settings import DeluxSettings
from analysis_data import build_settings
from odds_service import load_odds

# Get a match from queue
import sqlite3
con = sqlite3.connect('matches.db')
con.row_factory = sqlite3.Row
row = con.execute('SELECT match_id, sport FROM match_queue LIMIT 1').fetchone()
con.close()

if not row:
    print("[!] No match in queue")
    sys.exit(1)

match_id = row['match_id']
sport = row['sport']
print(f"Match: {match_id} (sport={sport})")

# Load queued match
queued = get_queued_match(match_id)
if not queued:
    print(f"[!] Match {match_id} not in queue")
    sys.exit(1)

match = queued.to_match_info()
print(f"  Teams: {match.home} vs {match.away}")

# Load settings
cfg = DeluxSettings.from_env()
ms = build_settings(
    sport=queued.sport,
    source=cfg.source,
    tz_base=cfg.tz_base,
    dayzone_base=cfg.dayzone_base,
    time_offset=cfg.time_offset,
)

# Load odds
code, odds_data = load_odds(match_id, cfg.source)
if code != 0 or odds_data is None:
    print(f"  [!] odds code={code}")
    odds_data = None

# Build payload
payload = load_analysis_data(match, ms)
print(f"  Payload: H2H={len(payload.h2h or [])}, Home={len(payload.home_all or [])}, Away={len(payload.away_all or [])}")
if payload.home_all:
    print(f"    Home first: {payload.home_all[0]}")
if payload.away_all:
    print(f"    Away first: {payload.away_all[0]}")

# Build store
store = CellStore()
formulas = load_sheet_formulas("", [
    "Incognito DATA", "Анализ", "Дома", "Гости", "ДомаДома", 
    "ДомаГости", "ГостиДома", "ГостиГости", "Очные", "ОчныеДГ",
    "Таблица", "Форма"
])
print(f"\nLoaded formulas for sheets: {list(formulas.keys())}")

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

# Apply payload
apply_payload_to_store(store, payload)
apply_settings_to_store(store, ms.sport, ms.source)
if odds_data:
    apply_odds_to_store(store, odds_data)
apply_queued_odds(store, None)

# Check what was written
from sheets_config import SHEET_HOME, SHEET_AWAY, SHEET_H2H

print(f"\n{SHEET_HOME} (Дома):")
print(f"  used_rows: {store.used_rows(SHEET_HOME)}")
for r in range(1, min(8, store.used_rows(SHEET_HOME) + 1)):
    vals = [store.get(SHEET_HOME, f"{c}{r}") for c in ['A','B','C','D','E','F','G','H','I']]
    print(f"  Row {r}: {vals}")

print(f"\n{SHEET_AWAY} (Гости):")
print(f"  used_rows: {store.used_rows(SHEET_AWAY)}")
for r in range(1, min(8, store.used_rows(SHEET_AWAY) + 1)):
    vals = [store.get(SHEET_AWAY, f"{c}{r}") for c in ['A','B','C','D','E','F','G','H','I']]
    print(f"  Row {r}: {vals}")

print(f"\nSHEET_H2H (Очные):")
print(f"  used_rows: {store.used_rows('Очные')}")
for r in range(1, min(8, store.used_rows('Очные') + 1)):
    vals = [store.get('Очные', f"{c}{r}") for c in ['A','B','C','D','E','F']]
    print(f"  Row {r}: {vals}")

# Check Incognito DATA
print(f"\nIncognito DATA:")
print(f"  A1={store.get('Incognito DATA', 'A1')!r}")
print(f"  I2={store.get('Incognito DATA', 'I2')!r}")
print(f"  S6={store.get('Incognito DATA', 'S6')!r}")
print(f"  T6={store.get('Incognito DATA', 'T6')!r}")
print(f"  U6={store.get('Incognito DATA', 'U6')!r}")

# Check if G16/L16 etc. have values
for addr in ['G16', 'L16', 'G17', 'L17', 'G20', 'L20']:
    print(f"  IncognitoData!{addr}={store.get('Incognito DATA', addr)!r}")

# Check Расчеты sheet
print(f"\nРасчеты sheet:")
print(f"  used_rows: {store.used_rows('Расчеты')}")
print(f"  A1={store.get('Расчеты', 'A1')!r}")

# Check if formulas exist for Incognito DATA!A1
print(f"\nIncognito DATA formulas:")
print(f"  A1 formula: {store.get_formula('Incognito DATA', 'A1')!r}")
print(f"  A1 value (constant): {store.get('Incognito DATA', 'A1')!r}")

# Check if Расчеты!A1 has a formula or constant
print(f"\nРасчеты formulas:")
print(f"  A1 formula: {store.get_formula('Расчеты', 'A1')!r}")
print(f"  A1 value: {store.get('Расчеты', 'A1')!r}")

print("\n=== Done ===")
