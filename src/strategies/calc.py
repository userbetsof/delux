"""Стратегии #1–3 считаются Python-calc (formula_port), не отдельными модулями."""

from __future__ import annotations

from typing import Optional

from src.strategies.base import MatchContext, Strategy, StrategySignal


class CalcStrategy(Strategy):
    """Обёртка над полями результата calc-движка (NTB / Betalone / Sniper)."""

    result_key: str

    def calculate_signals(self, ctx: MatchContext) -> Optional[StrategySignal]:
        results = ctx.extra.get("calc_results") or {}
        pred = str(results.get(self.result_key) or "").strip()
        if not pred or pred.startswith("#"):
            return None
        return StrategySignal(prediction=pred)


class NtbStrategy(CalcStrategy):
    id = 1
    name = "NTB"
    description = "DeluX NTB (лист Анализ S13 / Python calc)"
    result_key = "prediction_ntb"


class BetaloneStrategy(CalcStrategy):
    id = 2
    name = "Betalone"
    description = "DeluX Betalone (O10)"
    result_key = "prediction_betalone"


class SniperStrategy(CalcStrategy):
    id = 3
    name = "Sniper"
    description = "DeluX Sniper (X24)"
    result_key = "prediction_sniper"
