"""Test venue fix for away team history."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from analysis_data import load_analysis_data, build_settings
from match_store import get_queued_match
from settings import DeluxSettings
import sqlite3

# Get a match from queue
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
print(f"\n=== Home team (home_all) ===")
for m in payload.home_all[:3]:
    print(f"  {m.date} {m.home_name} vs {m.away_name} — venue={m.venue!r}")

print(f"\n=== Home team home matches (home_home) ===")
for m in payload.home_home[:3]:
    print(f"  {m.date} {m.home_name} vs {m.away_name} — venue={m.venue!r}")

print(f"\n=== Home team away matches (home_away) ===")
for m in payload.home_away[:3]:
    print(f"  {m.date} {m.home_name} vs {m.away_name} — venue={m.venue!r}")

print(f"\n=== Away team (away_all) ===")
for m in payload.away_all[:3]:
    print(f"  {m.date} {m.home_name} vs {m.away_name} — venue={m.venue!r}")

print(f"\n=== Away team home matches (away_home) ===")
for m in payload.away_home[:3]:
    print(f"  {m.date} {m.home_name} vs {m.away_name} — venue={m.venue!r}")

print(f"\n=== Away team away matches (away_away) ===")
for m in payload.away_away[:3]:
    print(f"  {m.date} {m.home_name} vs {m.away_name} — venue={m.venue!r}")

# Verify: home_home should all be "Дома", away_away should all be "Гости"
home_home_venues = set(m.venue for m in payload.home_home)
away_away_venues = set(m.venue for m in payload.away_away)

print(f"\n=== Verification ===")
print(f"home_home venues: {home_home_venues} (expected: {{'Дома'}})")
print(f"away_away venues: {away_away_venues} (expected: {{'Гости'}})")
print(f"home_home OK: {home_home_venues == {'Дома'}}")
print(f"away_away OK: {away_away_venues == {'Гости'}}")
