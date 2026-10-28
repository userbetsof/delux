import sqlite3
con = sqlite3.connect('matches.db')
con.row_factory = sqlite3.Row
rows = con.execute('SELECT match_id, home_team_id, away_team_id FROM matches LIMIT 5').fetchall()
for r in rows:
    print(f'{r["match_id"]}: {r["home_team_id"]} vs {r["away_team_id"]}')
con.close()
