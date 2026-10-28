"""Debug table_away for match Ипсвич vs Ноттингем."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from analysis_data import load_analysis_data, build_settings
from match_store import get_queued_match
from settings import DeluxSettings
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
print(f"table_overall: {len(payload.table_overall or [])} rows")
print(f"table_home: {len(payload.table_home or [])} rows")
print(f"table_away: {len(payload.table_away or [])} rows")

# Find teams in table_away
print(f"\n=== table_away ===")
for r in payload.table_away[:10]:
    team = r.team
    is_home = match.home in team
    is_away = match.away in team
    marker = " <-- HOME" if is_home else (" <-- AWAY" if is_away else "")
    if is_home or is_away:
        print(f"  {marker} {team}: P={r.played} W={r.wins} D={r.draws} L={r.losses}")

# Check if team name matches
print(f"\n=== Team name matching ===")
home_lower = match.home.casefold()
away_lower = match.away.casefold()
print(f"Home: {match.home!r} -> {home_lower}")
print(f"Away: {match.away!r} -> {away_lower}")

for r in payload.table_away[:20]:
    team = r.team
    team_lower = team.casefold()
    match_home = home_lower in team_lower or team_lower in home_lower
    match_away = away_lower in team_lower or team_lower in away_lower
    if match_home or match_away:
        print(f"  MATCH: {team!r} -> {team_lower} (home={match_home}, away={match_away})")
