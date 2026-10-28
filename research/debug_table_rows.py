"""Debug table_overall for match 4EFr4JFd - check _table_rows."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from analysis_data import load_analysis_data, build_settings
from match_store import get_queued_match
from settings import DeluxSettings
from formula_port.team_stats import _table_rows
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

# Check _table_rows
overall_rows = _table_rows(payload.table_overall)
print(f"\n_table_rows(payload.table_overall): {len(overall_rows)} rows")
if overall_rows:
    print(f"First row: {overall_rows[0]}")

# Check _compute_avg_rates
from formula_port.team_stats import _compute_avg_rates
rates = _compute_avg_rates(overall_rows)
print(f"\n_compute_avg_rates: {rates}")
if rates:
    avg_win, avg_draw, avg_away = rates
    print(f"  avg_win={avg_win:.4f} ({avg_win*100:.2f}%)")
    print(f"  avg_draw={avg_draw:.4f} ({avg_draw*100:.2f}%)")
    print(f"  avg_away={avg_away:.4f} ({avg_away*100:.2f}%)")
    print(f"  sum={avg_win+avg_draw+avg_away:.4f} ({(avg_win+avg_draw+avg_away)*100:.2f}%)")

# Check home rows
home_rows = _table_rows(payload.table_home)
print(f"\n_table_rows(payload.table_home): {len(home_rows)} rows")
home_rates = _compute_avg_rates(home_rows)
print(f"\n_compute_avg_rates (home): {home_rates}")
if home_rates:
    avg_win, avg_draw, avg_away = home_rates
    print(f"  avg_win={avg_win:.4f} ({avg_win*100:.2f}%)")
    print(f"  avg_draw={avg_draw:.4f} ({avg_draw*100:.2f}%)")
    print(f"  avg_away={avg_away:.4f} ({avg_away*100:.2f}%)")
    print(f"  sum={avg_win+avg_draw+avg_away:.4f} ({(avg_win+avg_draw+avg_away)*100:.2f}%)")
