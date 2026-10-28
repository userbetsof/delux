"""Бэктест XGBoost стратегии на исторических матчах из БД."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import json
from collections import defaultdict
from typing import Any, Dict, List

import pandas as pd
import joblib

from db import get_db_connection
from src.ml.config import load_config
from src.ml.database import DatabaseCatalog
from src.ml.features import build_feature_dataset
from src.ml.predict import _runs, CLASS_NAMES
from src.strategies.xgboost import SPORT_CONFIGS


def run_backtest(
    sport: int = 0,
    limit: int = 0,
    prob_min: float = 0.55,
    prob_max: float = 0.75,
    min_odds: float = 1.50,
) -> Dict[str, Any]:
    """
    Бэктест XGBoost стратегии на завершенных матчах.
    
    Args:
        sport: Вид спорта (0 = все)
        limit: Лимит матчей (0 = все)
        prob_min: Минимальная вероятность
        prob_max: Максимальная вероятность
        min_odds: Минимальные коэффициенты
    """
    print("=" * 80)
    print("XGBoost BACKTEST")
    print("=" * 80)
    print(f"  Sport: {sport if sport > 0 else 'ALL'}")
    print(f"  Limit: {limit if limit > 0 else 'ALL'}")
    print(f"  Prob range: {prob_min}-{prob_max}")
    print(f"  Min odds: {min_odds}")
    print()
    
    # Загружаем модель
    runs = _runs(model_type="xgboost", sport=sport) if sport > 0 else _runs(model_type="xgboost")
    
    if not runs:
        print("[!] Нет обученных моделей XGBoost!")
        return {"error": "no_models"}
    
    run = runs[0]
    model_path = run.get("artifact_path")
    target = run.get("target", "1x2")
    
    print(f"[+] Используем модель: {model_path}")
    print(f"    target: {target}")
    print()
    
    bundle = joblib.load(model_path)
    names = CLASS_NAMES[bundle.target]
    
    # Загружаем завершенные матчи
    with get_db_connection() as conn:
        query = """
            SELECT m.match_id, m.match_date, m.home_team_id, m.away_team_id,
                   m.score_home, m.score_away, m.sport,
                   ht.name as home_name, at.name as away_name,
                   l.name as league_name
            FROM matches m
            JOIN teams ht ON ht.id = m.home_team_id
            JOIN teams at ON at.id = m.away_team_id
            LEFT JOIN leagues l ON l.id = m.league_id
            WHERE m.match_status = 'Завершен'
              AND m.score_home IS NOT NULL AND m.score_away IS NOT NULL
              AND TRIM(m.match_id) != ''
        """
        
        params: list = []
        
        if sport > 0:
            query += " AND m.sport = ?"
            params.append(sport)
        
        query += " ORDER BY m.match_date DESC"
        
        if limit > 0:
            query += " LIMIT ?"
            params.append(limit)
        
        matches = conn.execute(query, params).fetchall()
    
    print(f"[+] Найдено завершенных матчей: {len(matches)}")
    print()
    
    # Строим фичи для всех матчей
    dataset = build_feature_dataset(
        DatabaseCatalog(),
        training=False,
        include_stacking=False,
    )
    frame = dataset.frame.copy()
    
    # Добавляем матчи из БД которых нет в фичах
    match_ids = [m[0] for m in matches]
    existing_ids = frame["match_id"].tolist()
    missing_ids = [mid for mid in match_ids if mid not in existing_ids]
    
    if missing_ids:
        print(f"[+] Добавляем {len(missing_ids)} матчей из БД...")
        # Создаем базовые фичи для отсутствующих матчей
        new_rows = []
        for match_id in missing_ids[:100]:  # Лимит для первых 100
            match_data = conn.execute(
                "SELECT match_id, match_date, start_ts AS match_start_ts, sport, league_id, "
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
                    "league_id": match_data["league_id"],
                    "home_team_id": match_data["home_team_id"],
                    "away_team_id": match_data["away_team_id"],
                    "home_name": match_data["home_name"] or "",
                    "away_name": match_data["away_name"] or "",
                    "score_home": match_data["score_home"] or 0,
                    "score_away": match_data["score_away"] or 0,
                })
        
        if new_rows:
            new_frame = pd.DataFrame(new_rows)
            frame = pd.concat([frame, new_frame], ignore_index=True)
    
    # Результаты бэктеста
    results = {
        "total": 0,
        "predicted": 0,
        "correct": 0,
        "by_sport": defaultdict(lambda: {
            "total": 0,
            "predicted": 0,
            "correct": 0,
            "probs": [],
            "odds": [],
        }),
        "by_outcome": defaultdict(lambda: {"total": 0, "correct": 0, "probs": [], "odds": []}),
        "detailed": [],
    }
    
    for match in matches:
        match_id, match_date, home_id, away_id, score_home, score_away, sport, home_name, away_name, league_name = match
        
        sport = int(sport)
        results["by_sport"][sport]["total"] += 1
        results["total"] += 1
        
        # Определяем реальный результат
        if score_home > score_away:
            actual = "П1"
        elif score_home < score_away:
            actual = "П2"
        else:
            actual = "X"
        
        # Ищем матч в фичах
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
        
        # Получаем коэффициенты
        if pred_label == "П1":
            market_name = "1X2_1"
        elif pred_label == "X":
            market_name = "1X2_X"
        else:
            market_name = "1X2_2"
        
        odds_row = conn.execute(
            "SELECT MAX(odds_value) as odds FROM odds WHERE match_id = ? AND market_name = ?",
            (match_id, market_name),
        ).fetchone()
        
        odds = float(odds_row["odds"]) if odds_row and odds_row["odds"] else None
        
        # Проверяем пороги
        config = SPORT_CONFIGS.get(sport, SPORT_CONFIGS[1])
        prob_min_actual = prob_min if prob_min > 0 else config["prob_min"]
        prob_max_actual = prob_max if prob_max > 0 else config["prob_max"]
        min_odds_actual = min_odds if min_odds > 0 else config["min_odds"]
        
        if pred_prob < prob_min_actual or pred_prob > prob_max_actual:
            continue
        
        if not odds or odds < min_odds_actual:
            continue
        
        # Предсказание прошло фильтр
        results["predicted"] += 1
        results["by_sport"][sport]["predicted"] += 1
        
        # Проверяем правильность
        is_correct = (pred_label == actual)
        if is_correct:
            results["correct"] += 1
            results["by_sport"][sport]["correct"] += 1
        
        results["by_outcome"][pred_label]["total"] += 1
        results["by_outcome"][pred_label]["probs"].append(pred_prob)
        results["by_outcome"][pred_label]["odds"].append(odds)
        if is_correct:
            results["by_outcome"][pred_label]["correct"] += 1
        
        # Детальный лог (первые 20)
        if len(results["detailed"]) < 20:
            results["detailed"].append({
                "match_id": match_id,
                "date": match_date,
                "home": home_name,
                "away": away_name,
                "league": league_name,
                "sport": sport,
                "prediction": pred_label,
                "probability": round(pred_prob, 3),
                "odds": round(odds, 2) if odds else None,
                "actual": actual,
                "score": f"{score_home}:{score_away}",
                "correct": is_correct,
            })
    
    conn.close()
    
    # Считаем метрики
    accuracy = results["correct"] / results["predicted"] if results["predicted"] > 0 else 0
    
    # ROI расчет
    if results["predicted"] > 0:
        total_stake = results["predicted"] * 100  # Ставка 100 на каждый матч
        total_win = sum(
            100 * odds 
            for d in results["detailed"] 
            if d["correct"] 
            and d["odds"]
        ) + (
            sum(
                100 * d["odds"]
                for d in results["detailed"][20:]  # Для матчей после 20-го
                if True  # Упрощение - считаем что точное количество правильных пропорционально
            )
        )
        
        # Более точный ROI по общему проценту
        win_count = results["correct"]
        lose_count = results["predicted"] - win_count
        avg_odds = sum(
            sum(results["by_outcome"][label]["odds"]) / len(results["by_outcome"][label]["odds"])
            for label in results["by_outcome"]
            if results["by_outcome"][label]["odds"]
        ) / len([l for l in results["by_outcome"] if results["by_outcome"][l]["odds"]]) if [l for l in results["by_outcome"] if results["by_outcome"][l]["odds"]] else 0
        
        total_payout = win_count * avg_odds * 100
        roi = ((total_payout - total_stake) / total_stake * 100) if total_stake > 0 else 0
    else:
        roi = 0
        avg_odds = 0
    
    # Вывод результатов
    print("=" * 80)
    print("РЕЗУЛЬТАТЫ")
    print("=" * 80)
    print(f"  Всего матчей:         {results['total']}")
    print(f"  Прошло фильтр:        {results['predicted']} ({results['predicted']/results['total']*100:.1f}%)" if results['total'] > 0 else "  Прошло фильтр:        0")
    print(f"  Правильных:           {results['correct']}")
    print(f"  Точность:             {accuracy*100:.2f}%")
    print(f"  Средний ROI:          {roi:.2f}%")
    print(f"  Средний коэффициент:  {avg_odds:.2f}")
    print()
    
    # По видам спорта
    print("-" * 80)
    print("ПО ВИДАМ СПОРТА:")
    print("-" * 80)
    print(f"  {'Sport':<10} {'Total':>8} {'Predicted':>10} {'Correct':>9} {'Accuracy':>10} {'Avg Prob':>10}")
    print("-" * 80)
    
    for sport_id in sorted(results["by_sport"].keys()):
        stats = results["by_sport"][sport_id]
        sport_accuracy = stats["correct"] / stats["predicted"] if stats["predicted"] > 0 else 0
        print(f"  {sport_id:<10} {stats['total']:>8} {stats['predicted']:>10} {stats['correct']:>9} {sport_accuracy*100:>9.2f}%")
    
    print()
    
    # По исходам
    print("-" * 80)
    print("ПО ИСХОДАМ:")
    print("-" * 80)
    print(f"  {'Outcome':<10} {'Total':>8} {'Correct':>9} {'Accuracy':>10} {'Avg Prob':>10} {'Avg Odds':>10}")
    print("-" * 80)
    
    for outcome in sorted(results["by_outcome"].keys()):
        stats = results["by_outcome"][outcome]
        outcome_accuracy = stats["correct"] / stats["total"] if stats["total"] > 0 else 0
        avg_p = sum(stats["probs"]) / len(stats["probs"]) if stats["probs"] else 0
        avg_o = sum(stats["odds"]) / len(stats["odds"]) if stats["odds"] else 0
        print(f"  {outcome:<10} {stats['total']:>8} {stats['correct']:>9} {outcome_accuracy*100:>9.2f}% {avg_p:>10.3f} {avg_o:>10.2f}")
    
    print()
    
    # Детальные матчи
    if results["detailed"]:
        print("-" * 80)
        print("ДЕТАЛЬНЫЕ МАТЧИ (первые 20):")
        print("-" * 80)
        for d in results["detailed"]:
            status = "✓" if d["correct"] else "✗"
            odds_str = f"@{d['odds']}" if d["odds"] else "@N/A"
            print(
                f"  {status} {d['home']} vs {d['away']} ({d['league']}) "
                f"| pred={d['prediction']} ({d['probability']}) {odds_str} "
                f"| actual={d['actual']} ({d['score']})"
            )
    
    print()
    print("=" * 80)
    
    return {
        "total": results["total"],
        "predicted": results["predicted"],
        "correct": results["correct"],
        "accuracy": accuracy,
        "roi": roi,
        "avg_odds": avg_odds,
        "by_sport": {str(k): v for k, v in results["by_sport"].items()},
        "by_outcome": {
            k: {
                "total": v["total"],
                "correct": v["correct"],
                "accuracy": v["correct"] / v["total"] if v["total"] > 0 else 0,
                "avg_prob": sum(v["probs"]) / len(v["probs"]) if v["probs"] else 0,
                "avg_odds": sum(v["odds"]) / len(v["odds"]) if v["odds"] else 0,
            }
            for k, v in results["by_outcome"].items()
        },
    }


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="XGBoost Backtest on historical matches")
    parser.add_argument("--sport", type=int, default=0, help="Sport ID (0=all)")
    parser.add_argument("--limit", type=int, default=0, help="Max matches to test")
    parser.add_argument("--prob-min", type=float, default=0, help="Min probability (0=default)")
    parser.add_argument("--prob-max", type=float, default=0, help="Max probability (0=default)")
    parser.add_argument("--min-odds", type=float, default=0, help="Min odds (0=default)")
    args = parser.parse_args()
    
    result = run_backtest(
        sport=args.sport,
        limit=args.limit,
        prob_min=args.prob_min,
        prob_max=args.prob_max,
        min_odds=args.min_odds,
    )
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
