from db import get_db_connection

with get_db_connection() as conn:
    cur = conn.cursor()
    
    # Check if Хиросима exists
    team = cur.execute('SELECT id, name FROM teams WHERE name LIKE "%Хиросима%"').fetchall()
    print(f'Teams with "Хиросима": {len(team)}')
    for t in team:
        print(f'  {t["id"]}: {t["name"]}')
        
        # Check matches
        matches = cur.execute("""
            SELECT match_id, match_date, home_team_id, away_team_id, score_home, score_away
            FROM matches
            WHERE (home_team_id = ? OR away_team_id = ?)
            ORDER BY match_date DESC
            LIMIT 5
        """, (t['id'], t['id'])).fetchall()
        
        print(f'  Matches: {len(matches)}')
        for m in matches:
            print(f'    {m["match_id"]} | {m["match_date"]} | {m["score_home"]}:{m["score_away"]}')
