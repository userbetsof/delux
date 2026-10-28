"""Check lookups.db schema."""
import sqlite3

con = sqlite3.connect('data/lookups.db')
rows = con.execute('PRAGMA table_info(lookup_values)').fetchall()
print('lookup_values columns:')
for r in rows:
    print(r)

con.close()
