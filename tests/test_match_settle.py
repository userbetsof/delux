from unittest import TestCase

from match_settle import is_finished_status, status_label
from result_checker import _scores_from_feed


class TestMatchSettle(TestCase):
    def test_flashscore_codes(self):
        self.assertEqual(status_label("1"), "Не начался")
        self.assertEqual(status_label("3"), "Завершен")
        self.assertEqual(status_label("33"), "8-й иннинг")

    def test_finished_only_when_complete(self):
        self.assertTrue(is_finished_status("Завершен", 2, 1))
        self.assertTrue(is_finished_status("После овертайма", 3, 2))
        self.assertFalse(is_finished_status("Не начался", 0, 0))
        self.assertFalse(is_finished_status("Неизвестный (1)", 0, 0))
        self.assertFalse(is_finished_status("Перенесен", 1, 0))
        self.assertFalse(is_finished_status("8-й иннинг", 5, 4))
        self.assertFalse(is_finished_status("Неизвестный (33)", 0, 5))
        self.assertTrue(is_finished_status("Не начался", 2, 1))
        self.assertTrue(is_finished_status("Неизвестный (3)", 1, 0))
        self.assertTrue(is_finished_status("", 3, 2))
        self.assertEqual(status_label("3.0"), "Завершен")

    def test_feed_scores_use_full_time(self):
        home, away = _scores_from_feed({"AT": "3", "AU": "1", "BC": "1", "BD": "1"})
        self.assertEqual((home, away), (3, 1))
