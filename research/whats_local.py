import json
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")

conn = sqlite3.connect(r"C:\papki\work\bets\delux\matches.db")
conn.row_factory = sqlite3.Row
MID = "6mdpltmc"

print("=== matches ===")
m = conn.execute(
    "SELECT match_id, match_date, match_status, prediction, start_ts, sport, "
    "score_home, score_away FROM matches WHERE match_id = ?",
    (MID,),
).fetchone()
print(dict(m) if m else "НЕТ")

print()
print("=== match_snapshot ===")
s = conn.execute(
    "SELECT standings_json IS NOT NULL AS st, form_json IS NOT NULL AS fm, "
    "h2h_json IS NOT NULL AS h2h, team_matches_json IS NOT NULL AS tm, "
    "length(standings_json) AS st_len, length(form_json) AS fm_len, "
    "length(h2h_json) AS h2h_len, length(team_matches_json) AS tm_len "
    "FROM match_snapshot WHERE match_id = ?",
    (MID,),
).fetchone()
print(dict(s) if s else "НЕТ СНИМКА")

print()
print("=== odds ===")
n = conn.execute("SELECT COUNT(*) FROM odds WHERE match_id = ?", (MID,)).fetchone()[0]
print(f"строк odds: {n}")

print()
print("=== team_matches_cache (история команд) ===")
rows = conn.execute(
    "SELECT * FROM team_matches_cache LIMIT 1"
).fetchone()
if rows:
    print("колонки:", list(rows.keys()))
cnt = conn.execute("SELECT COUNT(*) FROM team_matches_cache").fetchone()[0]
print("всего в кэше:", cnt)
