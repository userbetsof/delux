"""Debug match Qg22AywS - find the source of [Errno 22] Invalid argument."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

import traceback
import sqlite3

# Get match Qg22AywS
con = sqlite3.connect('matches.db')
con.row_factory = sqlite3.Row
row = con.execute('SELECT match_id, sport FROM match_queue WHERE match_id="Qg22AywS" LIMIT 1').fetchone()
con.close()

if not row:
    print("Match Qg22AywS not found!")
    sys.exit(1)

match_id = row['match_id']
sport = row['sport']
print(f"Match: {match_id}, sport: {sport}")

# Check start_ts
con = sqlite3.connect('matches.db')
con.row_factory = sqlite3.Row
queued = con.execute('SELECT start_ts, date_match, home, away FROM match_queue WHERE match_id=?', (match_id,)).fetchone()
con.close()

if queued:
    print(f"start_ts: {queued['start_ts']}")
    print(f"date_match: {queued['date_match']}")
    print(f"home: {queued['home']}")
    print(f"away: {queued['away']}")
    
    # Check if start_ts is valid
    if queued['start_ts']:
        from datetime import datetime, timezone
        try:
            dt = datetime.fromtimestamp(int(queued['start_ts']), tz=timezone.utc)
            print(f"start_ts as datetime: {dt}")
        except Exception as e:
            print(f"start_ts ERROR: {e}")
            traceback.print_exc()

# Try to fetch match status
from match_analysis import _fetch_match_status
try:
    status = _fetch_match_status(match_id, sport)
    print(f"\nMatch status: {status}")
except Exception as e:
    print(f"\nFetch status ERROR: {e}")
    traceback.print_exc()

# Try to fetch match score
from match_analysis import _fetch_match_score
try:
    sh, sa = _fetch_match_score(match_id, sport)
    print(f"Score: {sh}:{sa}")
except Exception as e:
    print(f"\nFetch score ERROR: {e}")
    traceback.print_exc()

# Try to load analysis data
from analysis_data import load_analysis_data, build_settings
from settings import DeluxSettings
try:
    from match_store import get_queued_match
    queued_obj = get_queued_match(match_id)
    match = queued_obj.to_match_info()
    cfg = DeluxSettings.from_env()
    ms = build_settings(sport=queued_obj.sport, source=cfg.source, tz_base=cfg.tz_base, dayzone_base=cfg.dayzone_base, time_offset=cfg.time_offset)
    
    payload = load_analysis_data(match, ms)
    print(f"\nPayload loaded: h2h={len(payload.h2h or [])}, home_all={len(payload.home_all or [])}, away_all={len(payload.away_all or [])}")
except Exception as e:
    print(f"\nLoad analysis ERROR: {e}")
    traceback.print_exc()
