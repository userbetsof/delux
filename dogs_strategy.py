"""Совместимость: реализация в src.strategies.dogs."""

from src.strategies.dogs import *  # noqa: F403
from src.strategies.dogs import (
    DOGS_STRATEGY_ID,
    MoneywayStrategy,
    build_moneyway_snapshot,
    compute_dogs_prediction,
    fetch_arbworld_index,
    get_arbworld_index,
    last_arbworld_error,
    _dogs_root,
)
