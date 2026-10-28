"""Debug бэктест: почему нет предсказаний."""

import sys
sys.path.insert(0, "C:/papki/work/bets/delux")

from db import get_db_connection
from src.ml.predict import _runs
from src.ml.features import build_feature_dataset
from src.ml.database import DatabaseCatalog
from src.ml.predict import CLASS_NAMES
import joblib

# Загружаем модель
runs = _runs(model_type="xgboost")
run = runs[0]
model_path = run.get("artifact_path")
print(f"Model: {model_path}")

bundle = joblib.load(model_path)
names = CLASS_NAMES[bundle.target]
print(f"Target: {bundle.target}, Names: {names}")

# Берем первый матч
with get_db_connection() as conn:
    match = conn.execute("""
        SELECT m.match_id, m.score_home, m.score_away, m.sport,
               ht.name as home_name, at.name as away_name
        FROM matches m
        JOIN teams ht ON ht.id = m.home_team_id
        JOIN teams at ON at.id = m.away_team_id
        WHERE m.match_status = 'Завершен'
          AND m.score_home IS NOT NULL AND m.score_away IS NOT NULL
        LIMIT 1
    """).fetchone()

match_id, score_home, score_away, sport, home_name, away_name = match
print(f"\nMatch: {match_id} | {home_name} vs {away_name} | {score_home}:{score_away} | sport={sport}")

# Проверяем фичи
dataset = build_feature_dataset(DatabaseCatalog(), training=False, include_stacking=False)
frame = dataset.frame

match_frame = frame[frame["match_id"] == match_id]
print(f"\nMatch in features: {not match_frame.empty}")
if not match_frame.empty:
    print(f"Features columns: {len(match_frame.columns)}")
    print(f"Sport in frame: {match_frame['sport'].iloc[0]}")

# Проверяем коэффициенты
odds = conn.execute(
    "SELECT market_name, MAX(odds_value) as odds FROM odds WHERE match_id = ? GROUP BY market_name",
    (match_id,)
).fetchall()
print(f"\nOdds in DB: {len(odds)} markets")
for o in odds:
    print(f"  {o[0]}: {o[1]}")

# Пробуем предсказание
if not match_frame.empty:
    probabilities = bundle.predict_proba(match_frame)
    predictions = bundle.predict(match_frame)
    
    position = 0
    pred_class = int(predictions[position])
    pred_label = names[pred_class]
    pred_prob = float(probabilities[position, pred_class])
    
    print(f"\nPrediction: {pred_label}, prob={pred_prob:.3f}")
    
    # Проверяем пороги
    from src.strategies.xgboost import SPORT_CONFIGS
    config = SPORT_CONFIGS.get(sport, SPORT_CONFIGS[1])
    print(f"Config: prob_min={config['prob_min']}, prob_max={config['prob_max']}, min_odds={config['min_odds']}")
    print(f"In prob range: {config['prob_min'] <= pred_prob <= config['prob_max']}")
