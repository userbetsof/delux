"""Оптимизация порогов XGBoost для baseball."""

import sys
sys.path.insert(0, "C:/papki/work/bets/delux")

import joblib
from collections import defaultdict
from db import get_db_connection
from src.ml.predict import _runs, CLASS_NAMES
from src.ml.features import build_feature_dataset
from src.ml.database import DatabaseCatalog


def analyze_baseball_thresholds():
    """Анализируем разные пороги для baseball."""
    
    # Загружаем модель для baseball
    runs = _runs(model_type="xgboost", sport=6)
    if not runs:
        print("Нет моделей для baseball!")
        return
    
    run = runs[0]
    bundle = joblib.load(run.get("artifact_path"))
    names = CLASS_NAMES[bundle.target]
    
    print("=" * 80)
    print("BASEBALL THRESHOLD OPTIMIZATION")
    print("=" * 80)
    
    # Загружаем завершенные матчи
    with get_db_connection() as conn:
        matches = conn.execute("""
            SELECT m.match_id, m.match_date, m.score_home, m.score_away,
                   ht.name as home_name, at.name as away_name
            FROM matches m
            JOIN teams ht ON ht.id = m.home_team_id
            JOIN teams at ON at.id = m.away_team_id
            WHERE m.sport = 6
              AND m.match_status = 'Завершен'
              AND m.score_home IS NOT NULL AND m.score_away IS NOT NULL
            ORDER BY m.match_date DESC
            LIMIT 200
        """).fetchall()
    
    print(f"[+] Найдено матчей: {len(matches)}")
    
    # Строим фичи
    dataset = build_feature_dataset(DatabaseCatalog(), training=False, include_stacking=False)
    frame = dataset.frame.copy()
    
    # Добавляем матчи из БД
    match_ids = [m[0] for m in matches]
    existing_ids = frame["match_id"].tolist()
    missing_ids = [mid for mid in match_ids if mid not in existing_ids]
    
    if missing_ids:
        import pandas as pd
        new_rows = []
        for match_id in missing_ids[:200]:
            match_data = conn.execute(
                "SELECT match_id, match_date, start_ts AS match_start_ts, sport, "
                "home_team_id, away_team_id, score_home, score_away, "
                "ht.name AS home_name, at.name AS away_name "
                "FROM matches m "
                "LEFT JOIN teams ht ON ht.id = m.home_team_id "
                "LEFT JOIN teams at ON at.id = m.away_team_id "
                "WHERE m.match_id = ?",
                (match_id,)
            ).fetchone()
            if match_data:
                new_rows.append({
                    "match_id": match_data["match_id"],
                    "match_date": match_data["match_date"],
                    "match_start_ts": match_data["match_start_ts"],
                    "sport": match_data["sport"],
                    "home_team_id": match_data["home_team_id"],
                    "away_team_id": match_data["away_team_id"],
                    "home_name": match_data["home_name"] or "",
                    "away_name": match_data["away_name"] or "",
                    "score_home": match_data["score_home"] or 0,
                    "score_away": match_data["score_away"] or 0,
                })
        if new_rows:
            frame = pd.concat([frame, pd.DataFrame(new_rows)], ignore_index=True)
    
    # Тестируем разные пороги
    prob_mins = [0.55, 0.60, 0.65, 0.70, 0.75]
    prob_maxs = [0.75, 0.80, 0.85, 0.90]
    min_odds_list = [1.50, 1.60, 1.70, 1.80, 1.90, 2.00]
    
    best_roi = -999
    best_config = None
    
    print("\nТестируем комбинации порогов:")
    print(f"{'Prob Min':>10} {'Prob Max':>10} {'Min Odds':>10} {'Predicted':>10} {'Correct':>10} {'Accuracy':>10} {'Avg Odds':>10} {'ROI':>10}")
    print("-" * 90)
    
    for prob_min in prob_mins:
        for prob_max in prob_maxs:
            for min_odds in min_odds_list:
                if prob_min >= prob_max:
                    continue
                
                results = {
                    "predicted": 0,
                    "correct": 0,
                    "total_odds": 0,
                    "odds_count": 0,
                }
                
                for match in matches:
                    match_id, match_date, score_home, score_away, home_name, away_name = match
                    
                    # Определяем реальный результат
                    if score_home > score_away:
                        actual = "П1"
                    elif score_home < score_away:
                        actual = "П2"
                    else:
                        actual = "X"
                    
                    # Ищем в фичах
                    match_frame = frame[frame["match_id"] == match_id]
                    if match_frame.empty:
                        continue
                    
                    # Предсказание
                    probabilities = bundle.predict_proba(match_frame)
                    predictions = bundle.predict(match_frame)
                    
                    position = 0
                    pred_class = int(predictions[position])
                    pred_label = names[pred_class]
                    pred_prob = float(probabilities[position, pred_class])
                    
                    # Проверяем пороги
                    if pred_prob < prob_min or pred_prob > prob_max:
                        continue
                    
                    # Получаем коэффициенты
                    if pred_label == "П1":
                        market_name = "1X2_1"
                    elif pred_label == "X":
                        market_name = "1X2_X"
                    else:
                        market_name = "1X2_2"
                    
                    odds_row = conn.execute(
                        "SELECT MAX(odds_value) as odds FROM odds WHERE match_id = ? AND market_name = ?",
                        (match_id, market_name)
                    ).fetchone()
                    
                    odds = float(odds_row["odds"]) if odds_row and odds_row["odds"] else None
                    
                    if not odds or odds < min_odds:
                        continue
                    
                    # Прошло фильтр
                    results["predicted"] += 1
                    
                    is_correct = (pred_label == actual)
                    if is_correct:
                        results["correct"] += 1
                    
                    results["total_odds"] += odds
                    results["odds_count"] += 1
                
                # Считаем метрики
                if results["predicted"] == 0:
                    continue
                
                accuracy = results["correct"] / results["predicted"]
                avg_odds = results["total_odds"] / results["odds_count"]
                
                # ROI: ставка 100 на каждый матч
                total_stake = results["predicted"] * 100
                total_payout = results["correct"] * avg_odds * 100
                roi = ((total_payout - total_stake) / total_stake * 100)
                
                print(
                    f"{prob_min:>10.2f} {prob_max:>10.2f} {min_odds:>10.2f} "
                    f"{results['predicted']:>10} {results['correct']:>10} "
                    f"{accuracy*100:>9.2f}% {avg_odds:>10.2f} {roi:>9.2f}%"
                )
                
                if roi > best_roi and results["predicted"] >= 10:
                    best_roi = roi
                    best_config = {
                        "prob_min": prob_min,
                        "prob_max": prob_max,
                        "min_odds": min_odds,
                        "accuracy": accuracy,
                        "predicted": results["predicted"],
                        "correct": results["correct"],
                        "avg_odds": avg_odds,
                        "roi": roi,
                    }
    
    print("\n" + "=" * 80)
    print("ЛУЧШАЯ КОМБИНАЦИЯ:")
    print("=" * 80)
    if best_config:
        print(f"  Prob Min:    {best_config['prob_min']}")
        print(f"  Prob Max:    {best_config['prob_max']}")
        print(f"  Min Odds:    {best_config['min_odds']}")
        print(f"  Predicted:   {best_config['predicted']}")
        print(f"  Correct:     {best_config['correct']}")
        print(f"  Accuracy:    {best_config['accuracy']*100:.2f}%")
        print(f"  Avg Odds:    {best_config['avg_odds']:.2f}")
        print(f"  ROI:         {best_config['roi']:.2f}%")
    else:
        print("  Нет подходящей комбинации с >= 10 предсказаний")


if __name__ == "__main__":
    analyze_baseball_thresholds()
