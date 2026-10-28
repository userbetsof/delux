"""Find Штутгарт and Боруссия М in table_overall."""
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
print(f"Home: {match.home}")
print(f"Away: {match.away}")

# Find teams in table_overall
print(f"\n=== table_overall ===")
for r in payload.table_overall:
    team = r.team
    is_home = match.home in team
    is_away = match.away in team
    marker = " <-- HOME" if is_home else (" <-- AWAY" if is_away else "")
    if is_home or is_away:
        played = int(r.played or 0)
        wins = int(r.wins or 0)
        draws = int(r.draws or 0)
        losses = int(r.losses or 0)
        win_rate = wins / played if played > 0 else 0
        draw_rate = draws / played if played > 0 else 0
        away_rate = losses / played if played > 0 else 0
        print(f"  {marker} {team}: P={played} W={wins} D={draws} L={losses}")
        print(f"         win_rate={win_rate:.4f} ({win_rate*100:.2f}%)")
        print(f"         draw_rate={draw_rate:.4f} ({draw_rate*100:.2f}%)")
        print(f"         away_rate={away_rate:.4f} ({away_rate*100:.2f}%)")
        print(f"         sum={win_rate+draw_rate+away_rate:.4f} ({(win_rate+draw_rate+away_rate)*100:.2f}%)")

# Find teams in table_home
print(f"\n=== table_home ===")
for r in payload.table_home:
    team = r.team
    is_home = match.home in team
    is_away = match.away in team
    marker = " <-- HOME" if is_home else (" <-- AWAY" if is_away else "")
    if is_home or is_away:
        played = int(r.played or 0)
        wins = int(r.wins or 0)
        draws = int(r.draws or 0)
        losses = int(r.losses or 0)
        win_rate = wins / played if played > 0 else 0
        draw_rate = draws / played if played > 0 else 0
        away_rate = losses / played if played > 0 else 0
        print(f"  {marker} {team}: P={played} W={wins} D={draws} L={losses}")
        print(f"         win_rate={win_rate:.4f} ({win_rate*100:.2f}%)")
        print(f"         draw_rate={draw_rate:.4f} ({draw_rate*100:.2f}%)")
        print(f"         away_rate={away_rate:.4f} ({away_rate*100:.2f}%)")
        print(f"         sum={win_rate+draw_rate+away_rate:.4f} ({(win_rate+draw_rate+away_rate)*100:.2f}%)")

# Find teams in table_away
print(f"\n=== table_away ===")
for r in payload.table_away:
    team = r.team
    is_home = match.home in team
    is_away = match.away in team
    marker = " <-- HOME" if is_home else (" <-- AWAY" if is_away else "")
    if is_home or is_away:
        played = int(r.played or 0)
        wins = int(r.wins or 0)
        draws = int(r.draws or 0)
        losses = int(r.losses or 0)
        win_rate = wins / played if played > 0 else 0
        draw_rate = draws / played if played > 0 else 0
        away_rate = losses / played if played > 0 else 0
        print(f"  {marker} {team}: P={played} W={wins} D={draws} L={losses}")
        print(f"         win_rate={win_rate:.4f} ({win_rate*100:.2f}%)")
        print(f"         draw_rate={draw_rate:.4f} ({draw_rate*100:.2f}%)")
        print(f"         away_rate={away_rate:.4f} ({away_rate*100:.2f}%)")
        print(f"         sum={win_rate+draw_rate+away_rate:.4f} ({(win_rate+draw_rate+away_rate)*100:.2f}%)")
