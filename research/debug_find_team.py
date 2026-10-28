"""Debug _find_team_in_table for away_rows."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from analysis_data import load_analysis_data, build_settings
from match_store import get_queued_match
from settings import DeluxSettings
from formula_port.team_stats import _table_rows, _find_team_in_table, _team_rates
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
print(f"table_away: {len(payload.table_away or [])} rows")

# Check _table_rows
away_rows = _table_rows(payload.table_away)
print(f"\n_away_rows: {len(away_rows)} rows")
if away_rows:
    print(f"First row: {away_rows[0]}")

# Check _find_team_in_table
away_team_row = _find_team_in_table(away_rows, match.away)
print(f"\n_find_team_in_table(away_rows, {match.away!r}):")
print(f"  Result: {away_team_row}")

if away_team_row:
    rates = _team_rates(away_team_row)
    print(f"  rates: {rates}")
    if rates:
        print(f"  win={rates[0]*100:.2f}%  draw={rates[1]*100:.2f}%  away={rates[2]*100:.2f}%")
