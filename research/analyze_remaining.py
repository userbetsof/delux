import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")

conn = sqlite3.connect(r"C:\papki\work\bets\delux\matches.db")
conn.row_factory = sqlite3.Row

rows = conn.execute(
    """
    SELECT o.match_id,
           SUM(CASE WHEN (o.home_win_prob + o.draw_prob + o.away_win_prob) > 0
                    THEN 1 ELSE 0 END) AS n,
           (SELECT COUNT(*) FROM match_snapshot s WHERE s.match_id = o.match_id) AS snap,
           (SELECT COUNT(*) FROM odds d WHERE d.match_id = o.match_id) AS odds
    FROM outcome_probabilities o
    GROUP BY o.match_id
    HAVING n < 10
    ORDER BY n
    """
).fetchall()

print(f"проблемных матчей: {len(rows)}")
print()
print("n/10 | снимок | odds | пример")
for r in rows[:20]:
    print(f"  {r['n']:2}/10 | {r['snap']}      | {r['odds']:4} | {r['match_id']}")

print()
no_snap = sum(1 for r in rows if r["snap"] == 0)
no_odds = sum(1 for r in rows if r["odds"] == 0)
print(f"из них без снимка: {no_snap}")
print(f"из них без odds:   {no_odds}")
print(f"без снимка И без odds: {sum(1 for r in rows if r['snap']==0 and r['odds']==0)}")
