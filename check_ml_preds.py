"""Check ml_predictions table."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from db import get_db_connection

with get_db_connection() as conn:
    # Check runs
    runs = conn.execute("""
        SELECT r.* FROM ml_runs r
        WHERE r.rowid = (
            SELECT MAX(x.rowid) FROM ml_runs x
            WHERE x.model_type=r.model_type AND x.target=r.target
        )
    """).fetchall()
    
    print(f"Found {len(runs)} runs:")
    for r in runs:
        d = dict(r)
        print(f"  {d['run_id'][:20]} | {d['model_type']:10s} | {d['target']:10s}")
    
    # Check predictions
    print(f"\nML predictions:")
    preds = conn.execute("""
        SELECT mp.run_id, mp.model_type, mp.target, mp.prediction, mp.probability_json,
               m.match_date, ht.name as home, at.name as away
        FROM ml_predictions mp
        JOIN matches m ON mp.match_id = m.match_id
        LEFT JOIN teams ht ON m.home_team_id = ht.id
        LEFT JOIN teams at ON m.away_team_id = at.id
        WHERE mp.model_type = 'xgboost'
        ORDER BY m.match_date DESC
        LIMIT 10
    """).fetchall()
    
    for p in preds:
        d = dict(p)
        print(f"  {d['match_id']} | {d['match_date']} | {d['prediction']:6s} | {d['target']:10s}")
        print(f"    probs: {d['probability_json'][:100]}")
