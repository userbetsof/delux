import sqlite3
import json

con = sqlite3.connect('matches.db')
con.row_factory = sqlite3.Row

# Get first match with outcome_probabilities
match_id = con.execute('''
    SELECT DISTINCT match_id FROM outcome_probabilities 
    WHERE strategy_id=1 AND home_win_prob > 0 
    LIMIT 1
''').fetchone()['match_id']

print(f"Match: {match_id}")

# Check match_snapshot
row = con.execute('SELECT * FROM match_snapshot WHERE match_id=?', (match_id,)).fetchone()
if row:
    keys = [d[0] for d in con.execute('PRAGMA table_info(match_snapshot)').fetchall()]
    print(f"\nSnapshot columns: {keys}")
    for k in keys:
        v = row[k]
        if v and isinstance(v, str) and len(v) > 100:
            print(f"  {k}: ({len(v)} chars) {v[:100]}...")
        elif v:
            print(f"  {k}: {v}")
else:
    print("No snapshot found")

con.close()
