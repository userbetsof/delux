import sys
sys.path.insert(0, "C:/papki/work/bets/delux")

from db import get_db_connection

with get_db_connection() as conn:
    # Проверим что модели есть в БД
    runs = conn.execute(
        "SELECT run_id, model_type, target, sport FROM ml_runs WHERE model_type='xgboost' ORDER BY sport, target"
    ).fetchall()
    
    print(f"Total XGBoost runs: {len(runs)}")
    for r in runs:
        print(f"  run={r[0][:12]}, type={r[1]}, target={r[2]}, sport={r[3]} (type={type(r[3]).__name__})")
    
    # Проверим запрос для sport=4
    print("\nQuery for sport=4:")
    rows = conn.execute("""
        SELECT r.* FROM ml_runs r
        WHERE r.rowid = (
            SELECT MAX(x.rowid) FROM ml_runs x
            WHERE x.model_type=r.model_type AND x.target=r.target AND x.sport=r.sport
        )
        AND r.model_type = ? AND r.sport = ?
    """, ("xgboost", 4)).fetchall()
    print(f"  Found: {len(rows)}")
