import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")

conn = sqlite3.connect(r"C:\papki\work\bets\delux\matches.db")
conn.row_factory = sqlite3.Row
MID = "6mdpltmc"

m = conn.execute("SELECT * FROM matches WHERE match_id = ?", (MID,)).fetchone()
print("matches:", dict(m) if m else "НЕТ")
print()

for table in (
    "match_snapshot",
    "strategy_predictions",
    "outcome_probabilities",
    "goal_probabilities",
    "odds",
    "match_queue",
):
    try:
        n = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE match_id = ?", (MID,)
        ).fetchone()[0]
        print(f"{table}: {n}")
    except Exception as exc:
        print(f"{table}: ERR {exc}")

print()
snap = conn.execute(
    "SELECT standings_json IS NOT NULL st, form_json IS NOT NULL fm, "
    "h2h_json IS NOT NULL h2h, team_matches_json IS NOT NULL tm, fetched_at "
    "FROM match_snapshot WHERE match_id = ?",
    (MID,),
).fetchone()
if snap:
    print(f"snapshot: standings={snap['st']} form={snap['fm']} "
          f"h2h={snap['h2h']} team_matches={snap['tm']} fetched={snap['fetched_at']}")
else:
    print("snapshot: НЕТ ЗАПИСИ")

print()
rows = conn.execute(
    "SELECT strategy_id, prediction, odds, result, profit "
    "FROM strategy_predictions WHERE match_id = ? ORDER BY strategy_id",
    (MID,),
).fetchall()
for r in rows:
    print(f"  #{r['strategy_id']} {r['prediction']!r} @{r['odds']} -> {r['result']}")
print(f"всего прогнозов: {len(rows)}")

print()
for table in ("outcome_probabilities", "goal_probabilities"):
    r = conn.execute(
        f"SELECT * FROM {table} WHERE match_id = ? LIMIT 1", (MID,)
    ).fetchone()
    if r:
        d = dict(r)
        print(f"{table}: " + ", ".join(
            f"{k}={v}" for k, v in d.items() if k != "match_id"
        )[:200])
    else:
        print(f"{table}: НЕТ")
