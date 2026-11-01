"""Реестр стратегий DeluX.

Временно отключены (станут отдельной программой):
  #5 Favorites, #6 StavkaTV, #7 Moneyway (dogs).
Чтобы вернуть — раскомментируйте импорты и строки в STRATEGY_CLASSES.
"""

from __future__ import annotations

from typing import Dict, List, Type

from src.strategies.base import Strategy
from src.strategies.bts import BtsStrategy
from src.strategies.calc import BetaloneStrategy, NtbStrategy, SniperStrategy
from src.strategies.dogs import MoneywayStrategy  # noqa: F401  (отключена)
from src.strategies.favorites import FavoritesStrategy  # noqa: F401  (отключена)
from src.strategies.onepr import OneprStrategy
from src.strategies.stavka_tv import StavkaTvStrategy  # noqa: F401  (отключена)
from src.strategies.whoscored import WhoscoredStrategy
from src.strategies.xgboost import XGBoostStrategy

STRATEGY_CLASSES: List[Type[Strategy]] = [
    NtbStrategy,
    BetaloneStrategy,
    SniperStrategy,
    BtsStrategy,
    # FavoritesStrategy,   # #5 — вынесено в отдельную программу
    # StavkaTvStrategy,    # #6 — вынесено в отдельную программу
    # MoneywayStrategy,    # #7 dogs — вынесено в отдельную программу
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
