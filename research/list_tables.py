import sqlite3
con = sqlite3.connect('matches.db')
con.row_factory = sqlite3.Row
tables = con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
for t in tables:
    print(t[0])
con.close()
