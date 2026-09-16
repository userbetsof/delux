from formula_port.parity import compare_calc_results, probs_close
from unittest import TestCase


class TestParityTol(TestCase):
    def test_one_percent(self):
        self.assertTrue(probs_close(0.40, 0.409))
        self.assertFalse(probs_close(0.40, 0.42))
        self.assertTrue(probs_close(40, 40.5))  # percents

    def test_compare_substrategies(self):
        def pack(h, d, a):
            return {"home_prob": h, "draw_prob": d, "away_prob": a}

        left = {
            "prediction_ntb": "П1",
            "prediction_betalone": "1X",
            "prediction_sniper": "П1",
            "outcome_probabilities": [pack(0.4, 0.3, 0.3)] * 10,
        }
        right = {
            "prediction_ntb": "П1",
            "prediction_betalone": "1X",
            "prediction_sniper": "П1",
            "outcome_probabilities": [pack(0.405, 0.301, 0.294)] * 10,
        }
        self.assertEqual(compare_calc_results(left, right), [])
        right["outcome_probabilities"][0] = pack(0.50, 0.3, 0.2)
        self.assertTrue(any("substrategy[0]" in x for x in compare_calc_results(left, right)))
