import sys
sys.path.insert(0, "C:/papki/work/bets/delux")

from src.ml.predict import _runs

for sport in [1, 4, 6]:
    runs = _runs(model_type="xgboost", sport=sport)
    print(f"Sport {sport}: {len(runs)} runs")
    for r in runs:
        print(f"  sport={r.get('sport')}, target={r.get('target')}, run={r.get('run_id', '')[:12]}")
