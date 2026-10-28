import sys
sys.path.insert(0, "C:/papki/work/bets/delux")

from db import get_db_connection

with get_db_connection() as conn:
    sports = conn.execute("""
        SELECT sport, COUNT(*) as cnt
        FROM matches
        WHERE match_status = 'Завершен'
          AND score_home IS NOT NULL
          AND score_away IS NOT NULL
          AND TRIM(match_id) != ''
        GROUP BY sport
    """).fetchall()
    
    print("Completed matches by sport:")
    for s in sports:
        print(f"  Sport {s[0]}: {s[1]} matches")
