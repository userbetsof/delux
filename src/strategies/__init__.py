"""Реестр стратегий DeluX."""

from __future__ import annotations

from typing import Dict, List, Type

from src.strategies.base import Strategy
from src.strategies.bts import BtsStrategy
from src.strategies.calc import BetaloneStrategy, NtbStrategy, SniperStrategy
from src.strategies.dogs import MoneywayStrategy
from src.strategies.favorites import FavoritesStrategy
from src.strategies.onepr import OneprStrategy
from src.strategies.stavka_tv import StavkaTvStrategy
from src.strategies.whoscored import WhoscoredStrategy
from src.strategies.xgboost import XGBoostStrategy

STRATEGY_CLASSES: List[Type[Strategy]] = [
    NtbStrategy,
    BetaloneStrategy,
    SniperStrategy,
    BtsStrategy,
    FavoritesStrategy,
    StavkaTvStrategy,
    MoneywayStrategy,
    OneprStrategy,
    WhoscoredStrategy,
    XGBoostStrategy,
]


def all_strategies() -> Dict[int, Strategy]:
    return {cls.id: cls() for cls in STRATEGY_CLASSES}


def get_strategy(strategy_id: int) -> Strategy:
    for cls in STRATEGY_CLASSES:
        if cls.id == strategy_id:
            return cls()
    raise KeyError(f"Unknown strategy id: {strategy_id}")
