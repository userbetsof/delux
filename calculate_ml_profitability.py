"""Calculate profitability of XGBoost predictions on TEST set only."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import json
import joblib
from pathlib import Path
from datetime import datetime

from db import get_db_connection, create_database
from src.ml.features import build_feature_dataset
from src.ml.database import DatabaseCatalog
from src.ml.config import load_config
from src.ml.predict import _runs, CLASS_NAMES
from src.ml.dataset import temporal_split

# --- Settings ---
STAKE = 100  # stake per bet in currency


def calculate_test_profitability():
    create_database()
    
    # Get latest XGBoost models
    runs = _runs(model_type="xgboost")
    if not runs:
        print("No XGBoost runs found!")
        return
    
    print(f"Found {len(runs)} XGBoost runs")
    
    # Build training dataset to get test split
    config = load_config()
    dataset = build_feature_dataset(DatabaseCatalog(), training=True, include_stacking=False)
    
    # Get test split (dates after training period)
    split = temporal_split(dataset, train_ratio=0.7, validation_ratio=0.15)
    test_ids = set(split.test["match_id"].tolist())
    train_ids = set(split.train["match_id"].tolist())
    
    print(f"\nData split:")
    print(f"  Train: {len(train_ids)} matches")
    print(f"  Validation: {len(split.validation)} matches")
    print(f"  Test: {len(test_ids)} matches")
    
    # Get test matches from DB with odds
    with get_db_connection() as conn:
        test_matches = conn.execute("""
            SELECT m.match_id, m.match_date, m.score_home, m.score_away,
                   ht.name as home_name, at.name as away_name,
                   o1.odds_value as odds_1, oX.odds_value as odds_x, o2.odds_value as odds_2,
                   oO.odds_value as odds_over_2_5, oU.odds_value as odds_under_2_5
            FROM matches m
            LEFT JOIN teams ht ON m.home_team_id = ht.id
            LEFT JOIN teams at ON m.away_team_id = at.id
            LEFT JOIN odds o1 ON m.match_id = o1.match_id AND o1.market_name = '1X2_1'
            LEFT JOIN odds oX ON m.match_id = oX.match_id AND oX.market_name = '1X2_X'
            LEFT JOIN odds o2 ON m.match_id = o2.match_id AND o2.market_name = '1X2_2'
            LEFT JOIN odds oO ON m.match_id = oO.match_id AND oO.market_name = 'OVER 2.5'
            LEFT JOIN odds oU ON m.match_id = oU.match_id AND oU.market_name = 'UNDER 2.5'
            WHERE m.match_id IN ({})
            ORDER BY m.match_date
        """.format(",".join("?" * len(test_ids))), list(test_ids)).fetchall()
    
    print(f"\nTest matches with odds: {len(test_matches)}")
    
    results = []
    for run in runs:
        run_id = run["run_id"]
        target = run["target"]
        model_type = run["model_type"]
        
        print(f"\n{'='*70}")
        print(f"Model: {model_type}/{target}")
        print(f"Run ID: {run_id}")
        print(f"{'='*70}")
        
        # Load model
        path = Path(str(run.get("artifact_path") or ""))
        if not path.exists():
            print(f"  Model file not found: {path}")
            continue
        
        bundle = joblib.load(path)
        
        # Filter test set
        test_frame = split.test[split.test["match_id"].isin([m["match_id"] for m in test_matches])].copy()
        
        if test_frame.empty:
            print(f"  No test matches in dataset")
            continue
        
        print(f"  Test matches in dataset: {len(test_frame)}")
        
        # Predict on test set
        probabilities = bundle.predict_proba(test_frame)
        predictions = bundle.predict(test_frame)
        names = CLASS_NAMES[bundle.target]
        
        # Create lookup
        match_lookup = {m["match_id"]: dict(m) for m in test_matches}
        
        # Calculate profitability
        bet_results = []
        for position, (_, row) in enumerate(test_frame.iterrows()):
            match_id = row["match_id"]
            match_data = match_lookup.get(match_id)
            if not match_data:
                continue
            
            score_home = int(row.get("score_home", 0) or 0)
            score_away = int(row.get("score_away", 0) or 0)
            total_goals = score_home + score_away
            
            # Determine actual outcome
            if target == "1x2":
                if score_home > score_away:
                    actual = "П1"
                elif score_home < score_away:
                    actual = "П2"
                else:
                    actual = "X"
            else:
                actual = "ТБ 2.5" if total_goals > 2.5 else "ТМ 2.5"
            
            # Get model prediction
            pred_class = int(predictions[position])
            prediction = names[pred_class]
            pred_prob = probabilities[position, pred_class]
            
            # Get odds
            odds_map = {
                "П1": match_data["odds_1"],
                "X": match_data["odds_x"],
                "П2": match_data["odds_2"],
                "ТБ 2.5": match_data["odds_over_2_5"],
                "ТМ 2.5": match_data["odds_under_2_5"],
            }
            odds = odds_map.get(prediction, 0)
            
            if odds is None:
                continue
            
            # Calculate profit
            won = prediction == actual
            profit = (odds - 1) * STAKE if won else -STAKE
            
            bet_results.append({
                "match_id": match_id,
                "date": str(row.get("match_date", "")),
                "teams": f"{match_data['home_name']} vs {match_data['away_name']}",
                "prediction": prediction,
                "actual": actual,
                "probability": pred_prob,
                "odds": odds,
                "stake": STAKE,
                "profit": profit,
                "won": won,
            })
        
        if not bet_results:
            print(f"  No test matches with odds")
            continue
        
        # Calculate statistics
        total_bets = len(bet_results)
        won_bets = sum(1 for b in bet_results if b["won"])
        win_rate = won_bets / total_bets * 100 if total_bets > 0 else 0
        total_profit = sum(b["profit"] for b in bet_results)
        avg_odds = sum(b["odds"] for b in bet_results) / total_bets if total_bets > 0 else 0
        avg_probability = sum(b["probability"] for b in bet_results) / total_bets if total_bets > 0 else 0
        roi = total_profit / (total_bets * STAKE) * 100 if total_bets > 0 else 0
        
        print(f"\n  Total bets: {total_bets}")
        print(f"  Won: {won_bets} ({win_rate:.1f}%)")
        print(f"  Lost: {total_bets - won_bets}")
        print(f"  Total profit: {total_profit:.2f}")
        print(f"  ROI: {roi:.1f}%")
        print(f"  Avg odds: {avg_odds:.2f}")
        print(f"  Avg probability: {avg_probability:.2f}")
        
        # Profit by probability range
        print(f"\n  Profit by probability range:")
        for prob_range, low, high in [("0.40-0.50", 0.40, 0.50),
                                       ("0.50-0.60", 0.50, 0.60),
                                       ("0.60-0.70", 0.60, 0.70),
                                       ("0.70+", 0.70, 1.0)]:
            range_preds = [b for b in bet_results if low <= b["probability"] < high]
            if range_preds:
                range_profit = sum(b["profit"] for b in range_preds)
                range_won = sum(1 for b in range_preds if b["won"])
                range_wr = range_won / len(range_preds) * 100
                print(f"    {prob_range}: {len(range_preds)} bets, {range_wr:.0f}% win, profit={range_profit:.2f}")
        
        # Show some predictions
        print(f"\n  Sample predictions:")
        for b in bet_results[:10]:
            status = "✓" if b["won"] else "✗"
            print(f"    {status} {b['teams'][:40]:40s} | {b['prediction']:4s} vs {b['actual']:4s} | {b['odds']:.2f} | {b['profit']:+.2f}")
        
        results.append({
            "run_id": run_id,
            "model_type": model_type,
            "target": target,
            "total_bets": total_bets,
            "won_bets": won_bets,
            "win_rate": win_rate,
            "total_profit": total_profit,
            "roi": roi,
            "avg_odds": avg_odds,
            "avg_probability": avg_probability,
        })
    
    # Summary table
    print(f"\n{'='*70}")
    print(f"SUMMARY (TEST SET - unbiased)")
    print(f"{'='*70}")
    print(f"{'Model':20s} {'Bets':>6s} {'Win%':>7s} {'Profit':>10s} {'ROI':>7s}")
    print(f"{'-'*52}")
    for r in results:
        print(f"{r['model_type']}/{r['target']:8s} {r['total_bets']:>6d} {r['win_rate']:>6.1f}% {r['total_profit']:>9.2f} {r['roi']:>6.1f}%")
    
    return results


if __name__ == "__main__":
    calculate_test_profitability()
