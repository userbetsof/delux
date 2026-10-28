"""Verify venue fix for match 4EFr4JFd (Боруссия М as away team)."""
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

if not row:
    print("Match 4EFr4JFd not found in queue!")
    sys.exit(1)

queued = get_queued_match(row['match_id'])
match = queued.to_match_info()

cfg = DeluxSettings.from_env()
ms = build_settings(sport=queued.sport, source=cfg.source, tz_base=cfg.tz_base, dayzone_base=cfg.dayzone_base, time_offset=cfg.time_offset)

payload = load_analysis_data(match, ms)

print(f"Match: {match.home} vs {match.away}")
print(f"Match ID: {match.match_id}")
print(f"Date: {match.date}")
print(f"Home participant ID: {match.home_participant_id}")
print(f"Away participant ID: {match.away_participant_id}")

# Find Боруссия М in the match
borussia = None
if 'Боруссия' in match.home:
    borussia = match.home
    print(f"\nБоруссия М is HOME team")
elif 'Боруссия' in match.away:
    borussia = match.away
    print(f"\nБоруссия М is AWAY team")

if not borussia:
    print("Боруссия М not found in this match!")
    sys.exit(1)

print(f"\n{'='*80}")
print(f"=== Checking Боруссия М data ===")
print(f"{'='*80}")

# Determine which payload fields belong to Боруссия М
if 'Боруссия' in match.home:
    all_matches = payload.home_all
    home_matches = payload.home_home
    away_matches = payload.home_away
else:
    all_matches = payload.away_all
    home_matches = payload.away_home
    away_matches = payload.away_away

print(f"\n--- Overall form (all matches for Боруссия М) ---")
for m in all_matches[:10]:
    expected_venue = "Дома" if borussia in (m.home_name, m.away_name) and m.home_name == borussia else "Гости"
    # Actually: venue is "Дома" if Боруссия М was the home team in that match
    if m.home_name == borussia:
        expected = "Дома"
    else:
        expected = "Гости"
    status = "✓" if m.venue == expected else "✗ WRONG"
    print(f"  {status} {m.date} {m.home_name} vs {m.away_name} — venue={m.venue!r} (expected={expected!r})")

print(f"\n--- Home form (Борус��ия М at home) ---")
for m in home_matches[:10]:
    expected = "Дома"
    status = "✓" if m.venue == expected else "✗ WRONG"
    print(f"  {status} {m.date} {m.home_name} vs {m.away_name} — venue={m.venue!r} (expected={expected!r})")

print(f"\n--- Away form (Боруссия М away) ---")
for m in away_matches[:10]:
    expected = "Гости"
    status = "✓" if m.venue == expected else "✗ WRONG"
    print(f"  {status} {m.date} {m.home_name} vs {m.away_name} — venue={m.venue!r} (expected={expected!r})")

# Verification
home_venues = set(m.venue for m in home_matches)
away_venues = set(m.venue for m in away_matches)

print(f"\n{'='*80}")
print(f"=== VERIFICATION ===")
print(f"{'='*80}")
print(f"home_matches venues: {home_venues} (expected: {{'Дома'}})")
print(f"away_matches venues: {away_venues} (expected: {{'Гости'}})")
print(f"home_matches OK: {home_venues == {'Дома'}}")
print(f"away_matches OK: {away_venues == {'Гости'}}")

# Check overall form too
overall_venues = set(m.venue for m in all_matches)
# Overall form should have both "Дома" and "Гости"
print(f"overall form venues: {overall_venues}")
print(f"overall form has correct mix: {'Дома' in overall_venues and 'Гости' in overall_venues}")
