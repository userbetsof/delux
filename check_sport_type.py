import sys
sys.path.insert(0, "C:/papki/work/bets/delux")

from db import get_db_connection

with get_db_connection() as conn:
    rows = conn.execute(
        "SELECT typeof(sport), sport FROM ml_runs LIMIT 3"
    ).fetchall()
    for r in rows:
        print(f"type={r[0]}, value={r[1]}")
