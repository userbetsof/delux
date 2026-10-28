import sys
sys.path.insert(0, "C:/papki/work/bets/delux")

from db import get_db_connection

with get_db_connection() as conn:
    runs = conn.execute(
        "SELECT sport, model_type, target, COUNT(*) as cnt "
        "FROM ml_runs GROUP BY sport, model_type, target"
    ).fetchall()
    print("Existing models:")
    for r in runs:
        print(f"  sport={r[0]}, {r[1]}, {r[2]}: {r[3]} models")
