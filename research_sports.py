"""Исследование: анализ точности XGBoost для каждого вида спорта."""

import sys
sys.path.insert(0, "C:/papki/work/bets/delux")

import json
from db import get_db_connection
from src.ml.predict import _runs
from src.ml.features import build_feature_dataset
from src.ml.database import DatabaseCatalog
import joblib
import pandas as pd
from collections import defaultdict


def analyze_existing_runs():
    """Анализируем существующие модели."""
    print("=" * 70)
    print("1. Существующие ML runs:")
    print("=" * 70)
    
    with get_db_connection() as conn:
        runs = conn.execute(
            "SELECT run_id, model_type, target, sport, metrics_json, artifact_path "
            "FROM ml_runs ORDER BY sport, model_type"
        ).fetchall()
        
        print(f"Всего моделей: {len(runs)}\n")
        
        for run in runs:
            run_id, model_type, target, sport, metrics_json, artifact_path = run
            metrics = json.loads(metrics_json) if metrics_json else {}
            print(f"  sport={sport}, {model_type}, {target}")
            print(f"    validation_accuracy: {metrics.get('validation_accuracy', 'N/A')}")
            print(f"    test_accuracy: {metrics.get('test_accuracy', 'N/A')}")
            print(f"    validation_brier: {metrics.get('validation_brier', 'N/A')}")
            print(f"    test_brier: {metrics.get('test_brier', 'N/A')}")
            print()


def analyze_predictions_by_sport():
    """Анализируем предсказания модели по видам спорта."""
    print("=" * 70)
    print("2. Анализ предсказаний по видам спорта:")
    print("=" * 70)
    
    # Загружаем модель
    runs = _runs(model_type="xgboost", sport=1)
    if not runs:
        print("Нет моделей XGBoost!")
        return
    
    run = runs[0]
    model_path = run.get("artifact_path")
    print(f"Используем модель: {model_path}")
    
    if not model_path:
        print("Нет artifact_path!")
        return
    
    bundle = joblib.load(model_path)
    names = {"1x2": {0: "X", 1: "П1", 2: "П2"}, "over_2_5": {0: "ТМ 2.5", 1: "ТБ 2.5"}}[bundle.target]
    
    # Строим фичи
    dataset = build_feature_dataset(
        DatabaseCatalog(),
        training=False,
        include_stacking=False,
    )
    frame = dataset.frame.copy()
    
    # Предсказания
    probabilities = bundle.predict_proba(frame)
    
    # Группируем по видам спорта
    sport_stats = defaultdict(lambda: {
        "count": 0,
        "predicted": defaultdict(int),
        "probabilities": [],
        "by_class": defaultdict(lambda: {"count": 0, "probs": []})
    })
    
    for i, (_, row) in enumerate(frame.iterrows()):
        sport = int(row.get("sport", 1))
        pred_class = bundle.predict(frame.iloc[i:i+1])[0]
        pred_label = names[pred_class]
        pred_prob = float(probabilities[i, pred_class])
        
        sport_stats[sport]["count"] += 1
        sport_stats[sport]["predicted"][pred_label] += 1
        sport_stats[sport]["probabilities"].append(pred_prob)
        sport_stats[sport]["by_class"][pred_label]["count"] += 1
        sport_stats[sport]["by_class"][pred_label]["probs"].append(pred_prob)
    
    for sport in sorted(sport_stats.keys()):
        stats = sport_stats[sport]
        print(f"\n  Sport {sport}: {stats['count']} матчей")
        print(f"    Распределение предсказаний:")
        for label, count in sorted(stats["predicted"].items()):
            print(f"      {label}: {count} ({count/stats['count']*100:.1f}%)")
        
        probs = stats["probabilities"]
        print(f"    Вероятности:")
        print(f"      min: {min(probs):.3f}")
        print(f"      max: {max(probs):.3f}")
        print(f"      mean: {sum(probs)/len(probs):.3f}")
        print(f"      median: {sorted(probs)[len(probs)//2]:.3f}")
        
        # Сколько предсказаний в диапазоне 0.55-0.70
        in_range = sum(1 for p in probs if 0.55 <= p <= 0.70)
        print(f"      В диапазоне 0.55-0.70: {in_range} ({in_range/len(probs)*100:.1f}%)")
        
        # По классам
        print(f"    По классам:")
        for label, class_stats in sorted(stats["by_class"].items()):
            probs_list = class_stats["probs"]
            print(f"      {label}: n={class_stats['count']}, prob_mean={sum(probs_list)/len(probs_list):.3f}")


def recommend_thresholds():
    """Рекомендуем пороги на основе анализа."""
    print("\n" + "=" * 70)
    print("3. Рекомендации по порогам:")
    print("=" * 70)
    
    # Для футбола (если есть данные)
    print("""
  На основе анализа предсказаний модели, нужно подобрать пороги:
  
  Ключевые метрики для каждого вида спорта:
  - mean probability: средняя вероятность предсказаний
  - % in 0.55-0.70: сколько матчей попадает в текущий диапазон
  - distribution: как распределены предсказания по классам
  
  Рекомендации по настройке:
  1. Если мало предсказаний в диапазоне -> widen пороги
  2. Если много предсказаний -> narrow пороги (повысить требования)
  3. Учитывать accuracy модели для каждого вида спорта
    """)


if __name__ == "__main__":
    analyze_existing_runs()
    analyze_predictions_by_sport()
    recommend_thresholds()
