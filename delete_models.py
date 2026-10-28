import sys
sys.path.insert(0, "C:/papki/work/bets/delux")

from db import get_db_connection

with get_db_connection() as conn:
    conn.execute("DELETE FROM ml_runs")
    conn.commit()
    print("Deleted all ml_runs")
