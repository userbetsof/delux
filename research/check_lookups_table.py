import sqlite3
con = sqlite3.connect('data/lookups.db')
rows = con.execute('''
    SELECT cell_key, value_text, value_num 
    FROM lookup_values 
    WHERE cell_key LIKE 'Таблица!M2%' OR cell_key LIKE 'Таблица!M3%'
''').fetchall()
print(f"Found {len(rows)} rows:")
for r in rows:
    print(f"  {r[0]}: text={r[1]} num={r[2]}")
con.close()
