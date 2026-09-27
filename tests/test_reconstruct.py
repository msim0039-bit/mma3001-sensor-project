import unittest
from datetime import datetime, timedelta

from src.reconstruct import reconstruct_gap


class TestReconstructGap(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2024, 3, 1, 12, 0)
        self.end = self.start + timedelta(minutes=30)
        self.missing = [
            self.start + timedelta(minutes=10),
            self.start + timedelta(minutes=20),
        ]

    def test_linear_recovers_known_straight_line(self):
        result = reconstruct_gap(
            self.start, 400, self.missing, self.end, 430, "linear"
        )
        self.assertEqual(result, [410.0, 420.0])

    def test_previous_uses_last_observed_value(self):
        result = reconstruct_gap(
            self.start, 400, self.missing, self.end, 430, "previous"
        )
        self.assertEqual(result, [400.0, 400.0])

    def test_rejects_time_outside_gap(self):
        with self.assertRaises(ValueError):
            reconstruct_gap(
                self.start, 400, [self.end], self.end, 430, "linear"
            )


if __name__ == "__main__":
    unittest.main()
