"""Debug match 238n0PMk - 1PR probabilities are all 0."""
import traceback, sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from match_analysis import analyze_match
from analysis_data import MatchInfo, build_settings
from match_store import QueuedMatch
from settings import DeluxSettings
import sqlite3

# Get match from matches table
con = sqlite3.connect('matches.db')
con.row_factory = sqlite3.Row
row = con.execute('SELECT match_id, sport, home_team_id, away_team_id, start_ts FROM matches WHERE match_id="238n0PMk"').fetchone()
con.close()

if not row:
    print("Match 238n0PMk not found!")
    sys.exit(1)

print(f"Match: {row['match_id']} | sport={row['sport']} | start_ts={row['start_ts']}")

# Get team names
con = sqlite3.connect('matches.db')
con.row_factory = sqlite3.Row
team_row = con.execute('SELECT t1.name as home, t2.name as away FROM matches m LEFT JOIN teams t1 ON m.home_team_id=t1.id LEFT JOIN teams t2 ON m.away_team_id=t2.id WHERE m.match_id="238n0PMk"').fetchone()
con.close()

if not team_row:
    print("Team names not found!")
    sys.exit(1)

print(f"Home: {team_row['home']} | Away: {team_row['away']}")

queued = QueuedMatch(
    match_id='238n0PMk',
    sport=row['sport'],
    home_name=team_row['home'],
    away_name=team_row['away'],
    tour_name=''
)
match = queued.to_match_info()

cfg = DeluxSettings.from_env()
ms = build_settings(sport=queued.sport, source=cfg.source, tz_base=cfg.tz_base, dayzone_base=cfg.dayzone_base, time_offset=cfg.time_offset)

try:
    results = analyze_match('', match, ms, queued=queued)
    print(f"\n=== Results ===")
    print(f"prediction_ntb: {results.get('prediction_ntb')}")
    print(f"prediction_sniper: {results.get('prediction_sniper')}")
    print(f"prediction_betalone: {results.get('prediction_betalone')}")
    
    # Check outcome probabilities
    outcome_probs = results.get('outcome_probabilities', [])
    if outcome_probs:
        print(f"\nOutcome probabilities ({len(outcome_probs)} strategies):")
        for op in outcome_probs[:5]:
            print(f"  #{op['strategy_idx']}: home={op['home_prob']:.4f} draw={op['draw_prob']:.4f} away={op['away_prob']:.4f}")
    else:
        print("\nNo outcome_probabilities!")
        
except Exception as e:
    traceback.print_exc()
