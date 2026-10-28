import sqlite3
con = sqlite3.connect('matches.db')
con.row_factory = sqlite3.Row

# Check outcome_probabilities for first 5 matches
rows = con.execute('''
    SELECT m.match_id, m.home_team_id, m.away_team_id,
           o.strategy_id, o.home_win_prob, o.draw_prob, o.away_win_prob
    FROM outcome_probabilities o
    JOIN matches m ON m.match_id = o.match_id
    WHERE m.match_id IN (
        SELECT match_id FROM matches LIMIT 5
    )
    ORDER BY m.match_id, o.strategy_id
    LIMIT 15
''').fetchall()

for r in rows:
    print(f'{r["match_id"]}: strat={r["strategy_id"]} H={r["home_win_prob"]:.2f} D={r["draw_prob"]:.2f} A={r["away_win_prob"]:.2f}')

# Check how many matches have outcome_probabilities
count = con.execute('SELECT COUNT(DISTINCT match_id) FROM outcome_probabilities').fetchone()[0]
print(f'\nTotal matches with outcome_probabilities: {count}')

# Check distinct probability sets
probs = con.execute('''
    SELECT DISTINCT 
        ROUND(home_win_prob, 2) as h,
        ROUND(draw_prob, 2) as d,
        ROUND(away_win_prob, 2) as a
    FROM outcome_probabilities
    WHERE strategy_id = 1
    ORDER BY h, d, a
''').fetchall()

print('\nDistinct probability sets for strategy_id=1:')
for p in probs:
    cnt = con.execute(
        'SELECT COUNT(*) FROM outcome_probabilities WHERE strategy_id=1 AND ROUND(home_win_prob,2)=? AND ROUND(draw_prob,2)=? AND ROUND(away_win_prob,2)=?',
        (p['h'], p['d'], p['a'])
    ).fetchone()[0]
    print(f'  H={p["h"]:.2f} D={p["d"]:.2f} A={p["a"]:.2f} -> {cnt} matches')

con.close()
