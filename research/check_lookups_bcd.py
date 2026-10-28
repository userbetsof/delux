"""Debug C2/D2/B2 in Incognito DATA for match 238n0PMk."""
import sqlite3

con = sqlite3.connect('data/lookups.db')
rows = con.execute('SELECT * FROM lookup_values WHERE cell_key LIKE ?', ('Incognito DATA!B%',)).fetchall()
print(f'Found {len(rows)} B* rows:')
for r in rows[:20]:
    print(r)

rows = con.execute('SELECT * FROM lookup_values WHERE cell_key LIKE ?', ('Incognito DATA!C%',)).fetchall()
print(f'\nFound {len(rows)} C* rows:')
for r in rows[:20]:
    print(r)

rows = con.execute('SELECT * FROM lookup_values WHERE cell_key LIKE ?', ('Incognito DATA!D%',)).fetchall()
print(f'\nFound {len(rows)} D* rows:')
for r in rows[:20]:
    print(r)

con.close()
