import sys
sys.path.insert(0, "C:/papki/work/bets/delux")

from db import get_db_connection

with get_db_connection() as conn:
    runs = conn.execute(
        "SELECT run_id, model_type, target, sport, artifact_path "
        "FROM ml_runs WHERE model_type='xgboost' ORDER BY sport, target"
    ).fetchall()
    
    print(f"Total XGBoost runs: {len(runs)}")
    for r in runs:
        print(f"  run={r[0][:12]}, type={r[1]}, target={r[2]}, sport={r[3]}, path={r[4][:50] if r[4] else 'None'}")
