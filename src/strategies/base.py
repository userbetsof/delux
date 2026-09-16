"""Единый контракт стратегий DeluX."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class MatchContext:
    """Контекст матча, который стратегии читают (без записи в БД)."""

    match_id: str
    home: str = ""
    away: str = ""
    sport: int = 1
    settings: Any = None
    odds_data: Any = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategySignal:
    """Нормализованный сигнал: прогноз + кф + заметки."""

    prediction: str
    odds: Optional[float] = None
    notes: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "prediction": self.prediction,
            "odds": self.odds,
            "notes": self.notes,
        }
        out.update(self.extra)
        return out

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> Optional["StrategySignal"]:
        if not data:
            return None
        pred = str(data.get("prediction") or "").strip()
        if not pred:
            return None
        extra = {k: v for k, v in data.items() if k not in ("prediction", "odds", "notes")}
        return cls(
            prediction=pred,
            odds=data.get("odds"),
            notes=data.get("notes"),
            extra=extra,
        )


class Strategy(ABC):
    """Базовый класс: id/name + evaluate(context) → сигнал или None."""

    id: int
    name: str
    description: str = ""

    def load_data(self, ctx: MatchContext) -> MatchContext:
        """Подгрузить внешние данные в ctx.extra. По умолчанию — no-op."""
        return ctx

    @abstractmethod
    def calculate_signals(self, ctx: MatchContext) -> Optional[StrategySignal]:
        """Посчитать сигнал. None = нет ставки."""

    def generate_bets(self, signal: StrategySignal, ctx: MatchContext) -> StrategySignal:
        """Постобработка (стейк, фильтры). По умолчанию сигнал без изменений."""
        return signal

    def evaluate(self, ctx: MatchContext) -> Optional[StrategySignal]:
        ctx = self.load_data(ctx)
        signal = self.calculate_signals(ctx)
        if signal is None:
            return None
        return self.generate_bets(signal, ctx)
