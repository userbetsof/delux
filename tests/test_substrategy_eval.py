"""Подстратегии не должны залипать на значениях из lookups.db."""

from __future__ import annotations

import unittest

from formula_port.cell_store import CellStore
from formula_port.engine import evaluate_dynamic_sheets


class TestSubstrategyEval(unittest.TestCase):
    def test_stale_lookup_does_not_freeze_1pr(self):
        store = CellStore()
        store.set_formula("Incognito DATA", "T32", "=0.1")
        store.set_formula("Incognito DATA", "T34", "=0.2")
        store.set_formula("Incognito DATA", "S6", "=T32+T34")
        store.set_formula("Анализ", "H8", "='Incognito DATA'!S6")
        # Ровно те константы, что лежат в lookups.db для S6/T32/T34.
        store.set_value("Incognito DATA", "S6", 0.5162409036297766)
        store.set_value("Incognito DATA", "T32", 0.3357032732447818)
        store.set_value("Incognito DATA", "T34", 0.07402791156272077)

        evaluate_dynamic_sheets(store, ["Incognito DATA", "Анализ"])

        self.assertAlmostEqual(float(store.get("Incognito DATA", "S6")), 0.3, places=6)
        self.assertAlmostEqual(float(store.get("Анализ", "H8")), 0.3, places=6)
        self.assertNotAlmostEqual(float(store.get("Анализ", "H8")), 0.51624, places=3)
