import sqlite3

conn = sqlite3.connect('matches.db')
cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='odds_history'")
print('Table exists:', cursor.fetchone() is not None)

cursor = conn.execute('PRAGMA table_info(odds_history)')
print('Columns:', [c[1] for c in cursor.fetchall()])

cursor = conn.execute("SELECT COUNT(*) FROM odds_history")
print('Rows:', cursor.fetchone()[0])

conn.close()
