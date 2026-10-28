"""Стратегия XGBoost 1x2: предсказания модели с вероятностью 0.55-0.70.

Поддерживает разные настройки для каждого вида спорта.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import joblib

from db import get_db_connection, create_database
from src.ml.config import load_config
from src.ml.database import DatabaseCatalog
from src.ml.features import build_feature_dataset
from src.ml.predict import _runs, CLASS_NAMES
from src.strategies.base import MatchContext, Strategy, StrategySignal

XGBOOST_STRATEGY_ID = 10

# Настройки для каждого вида спорта (обоснованы бэктестами, grid search 200 матчей)
SPORT_CONFIGS = {
    1: {
        "name": "Football",
        "prob_min": 0.55,
        "prob_max": 0.75,
        "min_odds": 1.50,
    },
    3: {
        "name": "Basketball",
        "prob_min": 0.55,
        "prob_max": 0.75,
        "min_odds": 1.45,
    },
    4: {
        "name": "Hockey",
        "prob_min": 0.55,
        "prob_max": 0.80,
        "min_odds": 1.55,
    },
    6: {
        "name": "Baseball",
        "prob_min": 0.55,  # Grid search: 0.55/0.80/1.50 = ROI +7.32% (лучший)
        "prob_max": 0.80,
        "min_odds": 1.50,
    },
}


class XGBoostStrategy(Strategy):
    id = XGBOOST_STRATEGY_ID
    name = "XGBoost"
    description = "XGBoost 1x2 — вероятность с учётом вида спорта"
    _DISABLED = True  # Временно отключена: низкая точность бэктеста

    def __init__(self):
        self._model = None
        self._model_path = None
        self._model_loaded = False
        self._sport_config = None
        self._sport = None
        if self._DISABLED:
            print("[XGBoost] DISABLED — no signals generated")

    def _load_model(self, sport: int) -> bool:
        """Загрузить последнюю модель XGBoost для вида спорта."""
        if self._model_loaded and self._sport == sport:
            return self._model is not None

        create_database()
        runs = _runs(model_type="xgboost", sport=sport)

        if not runs:
            self._model_loaded = True
            return False

        # Берём последнюю модель
        run = runs[0]
        self._model_path = Path(str(run.get("artifact_path") or ""))

        if not self._model_path.exists():
            self._model_loaded = True
            return False

        try:
            self._model = joblib.load(self._model_path)
            self._model_loaded = True
            self._sport = sport
            return True
        except Exception as e:
            print(f"[XGBoost] Failed to load model for sport {sport}: {e}")
            self._model_loaded = True
            return False

    def calculate_signals(self, ctx: MatchContext) -> Optional[StrategySignal]:
        """Получить предсказание XGBoost и отфильтровать по вероятности."""
        if self._DISABLED:
            return None
        
        sport = ctx.sport or 1
        
        # Получаем настройки для вида спорта
        config = SPORT_CONFIGS.get(sport)
        if not config:
            print(f"[XGBoost] No config for sport {sport}, using defaults")
            config = SPORT_CONFIGS[1]  # Football defaults
        
        self._sport_config = config
        self._sport = sport

        if not self._load_model(sport):
            return None

        if self._model is None:
            return None

        bundle = self._model
        names = CLASS_NAMES[bundle.target]

        # Строим фичи для текущего матча
        dataset = build_feature_dataset(
            DatabaseCatalog(),
            training=False,
            include_stacking=False,
        )
        frame = dataset.frame[dataset.frame["match_id"] == ctx.match_id].copy()

        if frame.empty:
            return None

        # Предсказание
        probabilities = bundle.predict_proba(frame)
        predictions = bundle.predict(frame)

        position = 0
        pred_class = int(predictions[position])
        prediction_label = names[pred_class]
        pred_prob = float(probabilities[position, pred_class])

        # Фильтр по вероятности (sport-specific)
        if pred_prob < config["prob_min"] or pred_prob > config["prob_max"]:
            return None

        # Получаем кф из контекста
        odds = self._get_odds(prediction_label, ctx)
        if not odds or odds < config["min_odds"]:
            return None

        return StrategySignal(
            prediction=prediction_label,
            odds=odds,
            notes=json.dumps({
                "model": "xgboost",
                "target": "1x2",
                "sport": sport,
                "sport_name": config["name"],
                "probability": round(pred_prob, 3),
                "probability_range": f"{config['prob_min']}-{config['prob_max']}",
                "min_odds": config["min_odds"],
            }, ensure_ascii=False),
            extra={
                "model_type": "xgboost",
                "target": "1x2",
                "probability": pred_prob,
                "sport": sport,
            },
        )

    def _get_odds(self, prediction: str, ctx: MatchContext) -> Optional[float]:
        """Получить кф для предсказания из контекста или БД."""
        # Сначала проверяем odds_data из контекста
        if ctx.odds_data:
            odds_map = {
                "П1": ("1X2_1", None),
                "X": ("1X2_X", None),
                "П2": ("1X2_2", None),
            }
            market_name, outcome = odds_map.get(prediction, (None, None))
            if market_name:
                for bk in getattr(ctx.odds_data, "bookmakers", []) or []:
                    market = bk.markets.get(market_name)
                    if market and market.current:
                        return float(market.current)

        # Fallback: загружаем из БД
        try:
            with get_db_connection() as conn:
                market_map = {
                    "П1": "1X2_1",
                    "X": "1X2_X",
                    "П2": "1X2_2",
                }
                market_name = market_map.get(prediction)
                if not market_name:
                    return None

                row = conn.execute(
                    "SELECT MAX(odds_value) as odds FROM odds WHERE match_id = ? AND market_name = ?",
                    (ctx.match_id, market_name),
                ).fetchone()

                if row and row["odds"]:
                    return float(row["odds"])
        except Exception:
            pass

        return None
