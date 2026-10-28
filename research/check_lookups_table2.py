import sqlite3
con = sqlite3.connect('data/lookups.db')
rows = con.execute('SELECT COUNT(*) FROM lookup_values WHERE cell_key LIKE "Таблица%"').fetchone()
print(f"Table lookups: {rows[0]}")

rows = con.execute('SELECT cell_key FROM lookup_values WHERE cell_key LIKE "Таблица%" LIMIT 20').fetchall()
for r in rows:
    print(f"  {r[0]}")
