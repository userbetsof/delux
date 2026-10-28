"""Debug table_overall for match 4EFr4JFd."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from analysis_data import load_analysis_data, build_settings
from match_store import get_queued_match
from settings import DeluxSettings
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

payload = load_analysis_data(match, ms)

print(f"Match: {match.home} vs {match.away}")
print(f"table_overall: {len(payload.table_overall or [])} rows")
print(f"table_home: {len(payload.table_home or [])} rows")
print(f"table_away: {len(payload.table_away or [])} rows")

if payload.table_overall:
    print(f"\nFirst 5 overall rows:")
    for r in payload.table_overall[:5]:
        print(f"  {r.rank} {r.team} P={r.played} W={r.wins} D={r.draws} L={r.losses}")

if payload.table_home:
    print(f"\nFirst 5 home rows:")
    for r in payload.table_home[:5]:
        print(f"  {r.rank} {r.team} P={r.played} W={r.wins} D={r.draws} L={r.losses}")

if payload.table_away:
    print(f"\nFirst 5 away rows:")
    for r in payload.table_away[:5]:
        print(f"  {r.rank} {r.team} P={r.played} W={r.wins} D={r.draws} L={r.losses}")
