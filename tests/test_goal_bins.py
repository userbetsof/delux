from unittest import TestCase

from formula_port.incodata_mc import GOAL_BINS, GOAL_MAX, _histogram
import random


class TestGoalBins(TestCase):
    def test_bins_are_0_to_12(self):
        self.assertEqual(GOAL_MAX, 12)
        self.assertEqual(GOAL_BINS, 13)

    def test_histogram_length_and_clip(self):
        rng = random.Random(0)
        hist = _histogram(2000, 8.0, 3.0, 8.0, 3.0, rng)
        self.assertEqual(len(hist), 13)
        self.assertGreater(sum(hist), 0)
        self.assertGreaterEqual(hist[12], 0)
