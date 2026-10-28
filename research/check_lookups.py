"""Check lookups.db for Incognito DATA values."""
import sqlite3

con = sqlite3.connect('data/lookups.db')
rows = con.execute('SELECT * FROM lookup_values WHERE key LIKE ?', ('Incognito DATA!G%',)).fetchall()
print(f'Found {len(rows)} rows:')
for r in rows[:20]:
    print(r)

con.close()
