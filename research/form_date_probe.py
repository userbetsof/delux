import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")

conn = sqlite3.connect(r"C:\papki\work\bets\delux\matches.db")
conn.row_factory = sqlite3.Row

row = conn.execute(
    "SELECT match_id, match_date, start_ts, match_status FROM matches WHERE match_id = ?",
    ("25Xg8KYr",),
).fetchone()
print("25Xg8KYr in matches:", dict(row) if row else "NOT IN matches")

total = conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
empty = conn.execute(
    "SELECT COUNT(*) FROM matches WHERE match_date IS NULL OR TRIM(match_date) = ''"
).fetchone()[0]
print(f"empty match_date: {empty} of {total}")

print("with start_ts but empty date:")
for r in conn.execute(
    "SELECT match_id, start_ts, match_status FROM matches "
    "WHERE (match_date IS NULL OR TRIM(match_date) = '') AND start_ts > 0 LIMIT 5"
):
    print("  ", dict(r))

# какие матчи из последних 5 у Расинга лежат в matches и с какой датой
print("\nПоследние матчи Расинга по matches (как их видит get_team_last_matches):")
for r in conn.execute(
    """
    SELECT m.match_id, m.match_date, m.start_ts
    FROM matches m
    JOIN teams ht ON ht.id = m.home_team_id
    JOIN teams at ON at.id = m.away_team_id
    WHERE (ht.name = 'Расинг' OR at.name = 'Расинг')
      AND m.match_status = 'Завершен' AND m.score_home IS NOT NULL
    ORDER BY m.match_date DESC LIMIT 6
    """
):
    print("  ", dict(r))
