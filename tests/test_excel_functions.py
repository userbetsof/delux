"""Unit-тесты Excel-функций."""

from __future__ import annotations

import math
import unittest

from formula_port.excel_functions import (
    COUNTIF,
    IF,
    IFERROR,
    INDEX,
    ISEVEN,
    LOOKUP,
    MATCH,
    POISSON,
    ROUNDDOWN,
    ROUNDUP,
    SUM,
    SUMIFS,
    TREND,
    VLOOKUP,
    _num,
    match_criteria,
)


class TestExcelFunctions(unittest.TestCase):
    def test_num_percent(self):
        self.assertAlmostEqual(_num("40%"), 0.4)

    def test_if(self):
        self.assertEqual(IF(True, "a", "b"), "a")
        self.assertEqual(IF(0, "a", "b"), "b")

    def test_iferror(self):
        self.assertEqual(IFERROR("#N/A", "RISK"), "RISK")
        self.assertEqual(IFERROR(5, 0), 5)

    def test_sum(self):
        self.assertEqual(SUM(1, 2, 3), 6)
        self.assertEqual(SUM([[1, 2], [3, 4]]), 10)

    def test_match_exact(self):
        self.assertEqual(MATCH(3, [1, 2, 3, 4], 0), 3)
        self.assertEqual(MATCH("id", [0, "id"], 0), 2)

    def test_index(self):
        table = [[10, 20], [30, 40]]
        self.assertEqual(INDEX(table, 2, 2), 40)

    def test_vlookup(self):
        table = [[1, "a"], [2, "b"], [5, "c"]]
        self.assertEqual(VLOOKUP(2, table, 2, False), "b")
        self.assertEqual(VLOOKUP(4, table, 2, True), "b")
        # Нельзя матчить "Орикс" с заголовком через _num(...)=0
        table2 = [["Команда", "Игр"], ["Орикс", 115], ["Ракутен", 53]]
        self.assertEqual(VLOOKUP("Орикс", table2, 2, False), 115)
        self.assertEqual(VLOOKUP("Нет", table2, 2, False), "#N/A")

    def test_poisson_pdf(self):
        val = POISSON(2, 1.5, False)
        expected = math.exp(-1.5) * (1.5 ** 2) / 2
        self.assertAlmostEqual(val, expected, places=6)

    def test_poisson_cdf(self):
        val = POISSON(2, 1.5, True)
        self.assertGreater(val, 0.5)
        self.assertLessEqual(val, 1.0)

    def test_trend(self):
        self.assertAlmostEqual(TREND([1, 2, 3], [1, 2, 3], 4), 4.0, places=6)

    def test_lookup(self):
        self.assertEqual(LOOKUP(0.3, [0, 0.2, 0.4], ["a", "b", "c"]), "b")

    def test_iseven_round(self):
        self.assertTrue(ISEVEN(2))
        self.assertFalse(ISEVEN(1.9))
        self.assertEqual(ROUNDDOWN(1.9, 0), 1)
        self.assertEqual(ROUNDUP(1.1, 0), 2)

    def test_sumifs_criteria(self):
        self.assertTrue(match_criteria(0.3, ">25%"))
        self.assertFalse(match_criteria(0.2, ">25%"))
        self.assertEqual(SUMIFS([1, 2, 3], [0.3, 0.1, 0.4], ">25%"), 4)
        # Пустые/0 не равны текстовому критерию «Дома»/«В»
        self.assertFalse(match_criteria(0, "Дома"))
        self.assertFalse(match_criteria("", "В"))
        self.assertFalse(match_criteria(None, "В"))
        self.assertTrue(match_criteria("В", "В"))
        self.assertEqual(COUNTIF([0, "", "Дома", 0], "Дома"), 1)

    def test_parse_sheet_ref_not_duplicated(self):
        from formula_port.refs import parse_formula_refs

        refs = parse_formula_refs("=Графики!BD39", "Анализ")
        keys = [r.key() for r in refs]
        self.assertEqual(keys, ["Графики!BD39"])


if __name__ == "__main__":
    unittest.main()
