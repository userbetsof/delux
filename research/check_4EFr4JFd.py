import sqlite3
con = sqlite3.connect('matches.db')
con.row_factory = sqlite3.Row

# Check match 4EFr4JFd
match = con.execute('SELECT * FROM matches WHERE match_id="4EFr4JFd"').fetchone()
if match:
    print("Match in DB:")
    for k, v in match.items():
        print(f"  {k}: {v}")
else:
    print("Match not found in matches")

# Check match_queue
match = con.execute('SELECT * FROM match_queue WHERE match_id="4EFr4JFd"').fetchone()
if match:
    print("\nMatch in queue:")
    for k, v in match.items():
        print(f"  {k}: {v}")
else:
    print("\nMatch not in queue")

con.close()
