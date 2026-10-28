"""Debug XGBoost predictions for today's matches."""
import sys
sys.path.insert(0, r'C:\papki\work\bets\delux')

import joblib
from pathlib import Path
from db import get_db_connection
from src.ml.features import build_feature_dataset
from src.ml.database import DatabaseCatalog
from src.ml.predict import _runs, CLASS_NAMES

# Load model
runs = _runs(model_type="xgboost")
xgboost_runs = [r for r in runs if r["target"] == "1x2"]
run = xgboost_runs[0]
model_path = Path(str(run.get("artifact_path") or ""))
bundle = joblib.load(model_path)
names = CLASS_NAMES[bundle.target]

print(f"Model: {bundle.model_type}/{bundle.target}")
print(f"Classes: {bundle.classes}")
print()

# Build dataset
dataset = build_feature_dataset(DatabaseCatalog(), training=False, include_stacking=False)

# Check today's matches
with get_db_connection() as conn:
    rows = conn.execute("""
        SELECT m.match_id, m.match_date, ht.name as home, at.name as away,
               o1.odds_value as odds_1, oX.odds_value as odds_x, o2.odds_value as odds_2
        FROM matches m
        LEFT JOIN teams ht ON m.home_team_id = ht.id
        LEFT JOIN teams at ON m.away_team_id = at.id
        LEFT JOIN odds o1 ON m.match_id = o1.match_id AND o1.market_name = '1X2_1'
        LEFT JOIN odds oX ON m.match_id = oX.match_id AND oX.market_name = '1X2_X'
        LEFT JOIN odds o2 ON m.match_id = o2.match_id AND o2.market_name = '1X2_2'
        WHERE m.match_date LIKE '2026.09.16%'
          AND m.sport = 1
        ORDER BY m.match_date
    """).fetchall()
    
    for r in rows:
        d = dict(r)
        match_id = d['match_id']
        home = d['home'] or ''
        away = d['away'] or ''
        
        frame = dataset.frame[dataset.frame["match_id"] == match_id].copy()
        if frame.empty:
            print(f"  SKIP {match_id} | {home[:20]:20s} vs {away[:20]:20s} | NOT IN DATASET")
            continue
        
        probabilities = bundle.predict_proba(frame)
        predictions = bundle.predict(frame)
        
        position = 0
        pred_class = int(predictions[position])
        prediction_label = names[pred_class]
        pred_prob = float(probabilities[position, pred_class])
        
        # Get odds
        odds_map = {"П1": d['odds_1'], "X": d['odds_x'], "П2": d['odds_2']}
        odds = odds_map.get(prediction_label)
        
        # Check filters
        prob_ok = 0.55 <= pred_prob <= 0.70
        odds_ok = odds is not None and odds >= 1.50
        
        print(f"  {match_id} | {home[:20]:20s} vs {away[:20]:20s}")
        print(f"    pred={prediction_label} prob={pred_prob:.3f} odds={odds:.2f if odds else 0:.2f}")
        print(f"    prob_ok={prob_ok} odds_ok={odds_ok}")
        
        if pred_prob > 0.70:
            print(f"    ⚠️  PROB TOO HIGH (>0.70)")
        elif pred_prob < 0.55:
            print(f"    ⚠️  PROB TOO LOW (<0.55)")
        if odds is None or odds < 1.50:
            print(f"    ⚠️  ODDS TOO LOW (<1.50)")
        print()
