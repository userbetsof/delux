"""Check payload.table_overall structure."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from analysis_data import load_analysis_data
from match_store import get_queued_match
from settings import DeluxSettings
from analysis_data import build_settings

# Get match
import sqlite3
con = sqlite3.connect('matches.db')
con.row_factory = sqlite3.Row
row = con.execute('SELECT match_id, sport FROM match_queue WHERE match_id="0tmcCQVh" LIMIT 1').fetchone()
if not row:
    row = con.execute('SELECT match_id, sport FROM match_queue LIMIT 1').fetchone()
con.close()

queued = get_queued_match(row['match_id'])
match = queued.to_match_info()

cfg = DeluxSettings.from_env()
ms = build_settings(sport=queued.sport, source=cfg.source, tz_base=cfg.tz_base, dayzone_base=cfg.dayzone_base, time_offset=cfg.time_offset)

payload = load_analysis_data(match, ms)

print(f"table_overall: {len(payload.table_overall or [])} rows")
if payload.table_overall:
    print(f"  first row type: {type(payload.table_overall[0])}")
    r = payload.table_overall[0]
    if hasattr(r, '__dict__'):
        print(f"  first row attrs: {r.__dict__}")
    elif isinstance(r, dict):
        print(f"  first row keys: {list(r.keys())}")
    else:
        print(f"  first row: {r}")

print(f"\ntable_home: {len(payload.table_home or [])} rows")
print(f"table_away: {len(payload.table_away or [])} rows")

# Check if match has standings data
print(f"\nMatch: {match.home} vs {match.away}")
print(f"League: {match.league}")
