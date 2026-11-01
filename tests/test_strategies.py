"""Tests for the unified Strategy contract."""

from __future__ import annotations

import unittest

from src.strategies.base import MatchContext, StrategySignal
from src.strategies.calc import NtbStrategy
from src.strategies import STRATEGY_CLASSES, all_strategies, get_strategy


class TestStrategyRegistry(unittest.TestCase):
    # #5 Favorites, #6 StavkaTV, #7 Moneyway временно отключены
    # (выносятся в отдельную программу), поэтому в реестре их нет.
    def test_registered_ids(self):
        ids = sorted(cls.id for cls in STRATEGY_CLASSES)
        self.assertEqual(ids, [1, 2, 3, 4, 8, 9, 10])

    def test_all_strategies_unique_ids(self):
        bag = all_strategies()
        self.assertEqual(len(bag), 7)
        self.assertEqual(get_strategy(8).name, "1pr")
        self.assertEqual(get_strategy(9).name, "WhoScored")

    def test_disabled_strategies_not_available(self):
        for sid in (5, 6, 7):
            with self.assertRaises(KeyError):
                get_strategy(sid)

    def test_ntb_from_calc_results(self):
        ctx = MatchContext(match_id="abc", extra={"calc_results": {"prediction_ntb": "П1"}})
        sig = NtbStrategy().evaluate(ctx)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.prediction, "П1")

    def test_ntb_skips_formula_error(self):
        ctx = MatchContext(match_id="abc", extra={"calc_results": {"prediction_ntb": "#VALUE!"}})
        self.assertIsNone(NtbStrategy().evaluate(ctx))

    def test_signal_from_dict(self):
        sig = StrategySignal.from_dict({"prediction": "X", "odds": 3.2, "notes": "{}"})
        self.assertEqual(sig.prediction, "X")
        self.assertEqual(sig.odds, 3.2)
        self.assertIsNone(StrategySignal.from_dict(None))
        self.assertIsNone(StrategySignal.from_dict({"prediction": ""}))


if __name__ == "__main__":
    unittest.main()
