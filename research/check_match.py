import sqlite3
con = sqlite3.connect('matches.db')
con.row_factory = sqlite3.Row

match_id = '0tmcCQVh'
rows = con.execute('''
    SELECT o.strategy_id, s.strategy_name, o.home_win_prob, o.draw_prob, o.away_win_prob
    FROM outcome_probabilities o
    JOIN sub_strategies s ON s.id = o.strategy_id
    WHERE o.match_id=?
    ORDER BY o.strategy_id
''', (match_id,)).fetchall()

print(f"Match: {match_id}")
for r in rows:
    print(f'  strat {r["strategy_id"]:2} {r["strategy_name"][:15]:15} H={r["home_win_prob"]:8.2f} D={r["draw_prob"]:8.2f} A={r["away_win_prob"]:8.2f}')

# Also check match info
match = con.execute('SELECT match_id, home_team_id, away_team_id, sport FROM matches WHERE match_id=?', (match_id,)).fetchone()
if match:
    print(f"\nMatch info: sport={match['sport']}, home={match['home_team_id']}, away={match['away_team_id']}")
else:
    print("\nMatch not found in matches table")

con.close()
