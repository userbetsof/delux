"""Check outcome_probabilities for strategy 1."""
import sqlite3

con = sqlite3.connect('matches.db')
con.row_factory = sqlite3.Row
rows = con.execute('SELECT * FROM outcome_probabilities WHERE match_id=? AND strategy_id=1', ('238n0PMk',)).fetchall()
print(f'Found {len(rows)} rows:')
for r in rows:
    print(dict(r))

con.close()
