"""Debug apply_payload_to_store for M30-M32."""
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

# Simulate apply_payload_to_store logic
overall_rows = _table_rows(payload.table_overall)
home_rows = _table_rows(payload.table_home)
away_rows = _table_rows(payload.table_away)

print(f"\noverall_rows: {len(overall_rows)} rows")
print(f"home_rows: {len(home_rows)} rows")
print(f"away_rows: {len(away_rows)} rows")

# M26-M28: rates хозяев из home таблицы
print(f"\n=== M26-M28 (home team rates) ===")
if home_rows:
    home_team_row = _find_team_in_table(home_rows, match.home)
    print(f"_find_team_in_table(home_rows, {match.home!r}): {home_team_row}")
    if home_team_row:
        rates = _team_rates(home_team_row)
        print(f"_team_rates: {rates}")
        if rates:
            for row_num, rate in zip((26, 27, 28), rates):
                print(f"  M{row_num} = {rate}")
        else:
            print("  rates is None!")
    else:
        print("  home_team_row is None!")
else:
    print("  home_rows is empty!")

# M30-M32: rates гостей из away таблицы
print(f"\n=== M30-M32 (away team rates) ===")
if away_rows:
    away_team_row = _find_team_in_table(away_rows, match.away)
    print(f"_find_team_in_table(away_rows, {match.away!r}): {away_team_row}")
    if away_team_row:
        rates = _team_rates(away_team_row)
        print(f"_team_rates: {rates}")
        if rates:
            for row_num, rate in zip((30, 31, 32), rates):
                print(f"  C{row_num} = {rate}")
        else:
            print("  rates is None!")
    else:
        print("  away_team_row is None!")
else:
    print("  away_rows is empty!")
