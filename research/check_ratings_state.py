import os
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")

path = os.environ.get("DATABASE_PATH") or r"C:\papki\work\bets\delux\matches.db"
conn = sqlite3.connect(path)

checks = (
    ("team_elo_ratings", "rating = 1500 AND matches_played = 0"),
    ("glicko2_ratings", "rating = 1500 AND rd = 350 AND matches_played = 0"),
    ("openskill_ratings", "mu = 25 AND matches_played = 0"),
)
print(f"DB: {path}")
for table, cond in checks:
    total = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
    ok = conn.execute(f'SELECT COUNT(*) FROM "{table}" WHERE {cond}').fetchone()[0]
    print(f"  {table:22} {ok}/{total} в исходном состоянии")

for table in ("elo_rating_history", "glicko2_rating_history", "openskill_rating_history"):
    n = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
    print(f"  {table:22} history rows = {n}")
conn.close()
