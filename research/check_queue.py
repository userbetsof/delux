import sqlite3
con = sqlite3.connect('matches.db')
con.row_factory = sqlite3.Row

# Check match_queue schema
cols = [d[1] for d in con.execute('PRAGMA table_info(match_queue)').fetchall()]
print(f"match_queue columns: {cols}")

# Check match_queue data
rows = con.execute('SELECT * FROM match_queue LIMIT 3').fetchall()
print("\nmatch_queue data:")
for r in rows:
    print(f"  {dict(r)}")

# Check matches
cols = [d[1] for d in con.execute('PRAGMA table_info(matches)').fetchall()]
print(f"\nmatches columns: {cols}")

rows = con.execute('SELECT match_id FROM matches WHERE sport=1 LIMIT 3').fetchall()
print("\nmatches sport=1:")
for r in rows:
    print(f"  {r['match_id']}")

con.close()
