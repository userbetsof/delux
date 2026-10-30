import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")

conn = sqlite3.connect(r"C:\papki\work\bets\delux\matches.db")
conn.row_factory = sqlite3.Row
MID = "6mdpltmc"

print("=== outcome_probabilities по стратегиям ===")
for r in conn.execute(
    "SELECT strategy_id, home_win_prob, draw_prob, away_win_prob "
    "FROM outcome_probabilities WHERE match_id = ? ORDER BY strategy_id",
    (MID,),
):
    print(
        f"  #{r['strategy_id']}: home={r['home_win_prob']} "
        f"draw={r['draw_prob']} away={r['away_win_prob']}"
    )

print()
print("=== сравним с другим матчем, где всё ок ===")
other = conn.execute(
    "SELECT match_id, strategy_id, home_win_prob, draw_prob, away_win_prob "
    "FROM outcome_probabilities WHERE (home_win_prob + draw_prob + away_win_prob) > 0 "
    "LIMIT 3"
).fetchall()
for r in other:
    print(
        f"  {r['match_id']} #{r['strategy_id']}: {r['home_win_prob']:.1f} "
        f"{r['draw_prob']:.1f} {r['away_win_prob']:.1f}"
    )

print()
print("=== сколько всего матчей с нулевыми вероятностями ===")
zero = conn.execute(
    "SELECT COUNT(DISTINCT match_id) FROM outcome_probabilities "
    "WHERE (home_win_prob + draw_prob + away_win_prob) = 0 OR home_win_prob IS NULL"
).fetchone()[0]
total = conn.execute("SELECT COUNT(DISTINCT match_id) FROM outcome_probabilities").fetchone()[0]
print(f"  нулевых: {zero} из {total}")
