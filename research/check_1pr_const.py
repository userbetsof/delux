import sqlite3
con = sqlite3.connect('file:matches.db?mode=ro', uri=True)
con.row_factory = sqlite3.Row
print('=== "1 пр" (strategy_id=1) по разным матчам ===')
for r in con.execute('''SELECT o.match_id, o.home_win_prob, o.draw_prob, o.away_win_prob
    FROM outcome_probabilities o WHERE o.strategy_id=1 ORDER BY o.match_id LIMIT 15'''):
    print(f"  {r['match_id']}: {r['home_win_prob']:.2f} / {r['draw_prob']:.2f} / {r['away_win_prob']:.2f}")
con.close()
