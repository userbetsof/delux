import sys
sys.path.insert(0, "C:/papki/work/bets/delux")

from db import get_db_connection

with get_db_connection() as conn:
    # Обновим sport на INTEGER
    conn.execute("UPDATE ml_runs SET sport = CAST(sport AS INTEGER)")
    conn.commit()
    
    # Проверим
    rows = conn.execute(
        "SELECT sport, COUNT(*) FROM ml_runs GROUP BY sport"
    ).fetchall()
    print("Models by sport:")
    for r in rows:
        print(f"  sport={r[0]} ({type(r[0]).__name__}): {r[1]} models")
