"""Test M26-M32 for multiple matches."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from formula_port.workbook_loader import load_sheet_formulas, load_sheet_constants
from formula_port.cell_store import CellStore
from formula_port.team_stats import apply_payload_to_store, apply_settings_to_store
from analysis_data import load_analysis_data, build_settings
from match_store import get_queued_match
from settings import DeluxSettings
from sheets_config import DYNAMIC_SHEETS, SHEET_TABLE
import sqlite3

# Get all matches from queue
con = sqlite3.connect('matches.db')
con.row_factory = sqlite3.Row
rows = con.execute('SELECT match_id, sport FROM match_queue LIMIT 5').fetchall()
con.close()

for row in rows:
    match_id = row['match_id']
    sport = row['sport']
    
    queued = get_queued_match(match_id)
    match = queued.to_match_info()
    
    cfg = DeluxSettings.from_env()
    ms = build_settings(sport=queued.sport, source=cfg.source, tz_base=cfg.tz_base, dayzone_base=cfg.dayzone_base, time_offset=cfg.time_offset)
    
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
    
    m26 = store.get(SHEET_TABLE, 'M26')
    m27 = store.get(SHEET_TABLE, 'M27')
    m28 = store.get(SHEET_TABLE, 'M28')
    m30 = store.get(SHEET_TABLE, 'M30')
    m31 = store.get(SHEET_TABLE, 'M31')
    m32 = store.get(SHEET_TABLE, 'M32')
    
    sum_m26_28 = (m26 or 0) + (m27 or 0) + (m28 or 0)
    sum_m30_32 = (m30 or 0) + (m31 or 0) + (m32 or 0)
    
    print(f"\n=== {match.home} vs {match.away} ===")
    print(f"  M26={m26:.4f} ({m26*100:.2f}%)  M27={m27:.4f} ({m27*100:.2f}%)  M28={m28:.4f} ({m28*100:.2f}%)  sum={sum_m26_28:.4f} ({sum_m26_28*100:.2f}%)")
    print(f"  M30={m30:.4f} ({m30*100:.2f}%)  M31={m31:.4f} ({m31*100:.2f}%)  M32={m32:.4f} ({m32*100:.2f}%)  sum={sum_m30_32:.4f} ({sum_m30_32*100:.2f}%)")
    print(f"  Different: {abs(sum_m26_28 - sum_m30_32) > 0.01}")
