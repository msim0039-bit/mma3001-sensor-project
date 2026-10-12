"""Verification tests for cubic spline and CO2 regression models."""

import sys
import unittest
from pathlib import Path

import numpy as np

# Allow tests to import source files when run from the repository.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from models import cubic_spline_predict, fit_regression


class TestCubicSpline(unittest.TestCase):
    """Check spline accuracy and input validation."""

    def test_straight_line_at_uneven_times(self):
        """A natural spline must reproduce a straight line."""
        predictions = cubic_spline_predict(
            [0, 2, 5, 9, 12, 16],
            [400, 404, 410, 418, 424, 432],
            [3, 6, 10],
        )
        np.testing.assert_allclose(
            predictions, [406, 412, 420], rtol=0, atol=1e-9
        )

    def test_reproduces_observed_values(self):
        """The spline must pass through its supplied observations."""
        times = [0, 2, 5, 9]
        values = [410, 450, 420, 470]
        predictions = cubic_spline_predict(times, values, times)
        np.testing.assert_allclose(
            predictions, values, rtol=0, atol=1e-9
        )

    def test_rejects_invalid_observations(self):
        """Invalid shapes, ordering, and values must raise ValueError."""
        cases = [
            ([0], [400], [0]),
            ([0, 1], [400], [0.5]),
            ([0, 0], [400, 410], [0]),
            ([1, 0], [400, 410], [0.5]),
            ([0, np.nan], [400, 410], [0.5]),
            ([0, 1], [400, np.inf], [0.5]),
            ([[0, 1]], [400, 410], [0.5]),
        ]
        for times, values, queries in cases:
            with self.subTest(times=times, values=values):
                with self.assertRaises(ValueError):
                    cubic_spline_predict(times, values, queries)

    def test_rejects_invalid_queries(self):
        """Queries must be finite, one-dimensional, and in range."""
        for queries in ([-1], [3], [np.nan], [np.inf], [[1]]):
            with self.subTest(queries=queries):
                with self.assertRaises(ValueError):
                    cubic_spline_predict(
                        [0, 2], [400, 420], queries
                    )


class TestCO2Regression(unittest.TestCase):
    """Check regression against an independently specified equation."""

    def setUp(self):
        # Independently varying features give a full-rank design.
        self.features = np.array([
            [20, 40, 1000],
            [22, 40, 1000],
            [20, 50, 1000],
            [20, 40, 1010],
            [22, 50, 1010],
            [21, 45, 1005],
        ], dtype=float)

        # Known synthetic relationship, with CO2 in ppm:
        # CO2 = 400 + 2*(T-20) + 0.5*(H-40) - 0.1*(P-1000)
        self.target = (
            400
            + 2 * (self.features[:, 0] - 20)
            + 0.5 * (self.features[:, 1] - 40)
            - 0.1 * (self.features[:, 2] - 1000)
        )
        self.model = fit_regression(self.features, self.target)

    def test_predicts_known_equation_on_new_rows(self):
        """New feature combinations must match hand-calculated CO2."""
        new_features = [
            [21, 44, 1002],
            [23, 46, 1008],
        ]
        predictions = self.model.predict(new_features)
        np.testing.assert_allclose(
            predictions, [403.8, 408.2], rtol=0, atol=1e-9
        )

    def test_prediction_does_not_refit_scaling(self):
        """A prediction must not depend on other prediction rows."""
        mean_before = self.model.feature_mean.copy()
        scale_before = self.model.feature_scale.copy()

        single = self.model.predict([[21, 44, 1002]])
        batch = self.model.predict([
            [21, 44, 1002],
            [28, 75, 1020],
        ])

        np.testing.assert_allclose(
            single[0], batch[0], rtol=0, atol=1e-9
        )
        np.testing.assert_array_equal(
            self.model.feature_mean, mean_before
        )
        np.testing.assert_array_equal(
            self.model.feature_scale, scale_before
        )

    def test_rejects_invalid_prediction_features(self):
        """Prediction requires finite values and three columns."""
        cases = [
            [[20, 40]],
            [20, 40, 1000],
            [[20, np.nan, 1000]],
            [[20, 40, np.inf]],
        ]
        for features in cases:
            with self.subTest(features=features):
                with self.assertRaises(ValueError):
                    self.model.predict(features)

    def test_rejects_invalid_training_data(self):
        """Training requires matching, finite targets and valid features."""
        invalid_features = self.features.copy()
        invalid_features[0, 0] = np.nan

        invalid_target = self.target.copy()
        invalid_target[0] = np.inf

        cases = [
            (self.features[:, :2], self.target),
            (invalid_features, self.target),
            (self.features, self.target[:-1]),
            (self.features, self.target.reshape(-1, 1)),
            (self.features, invalid_target),
            (self.features[:3], self.target[:3]),
        ]
        for features, target in cases:
            with self.subTest(shape=np.shape(features)):
                with self.assertRaises(ValueError):
                    fit_regression(features, target)

    def test_rejects_constant_feature(self):
        """A feature with zero training variation must be rejected."""
        features = self.features.copy()
        features[:, 2] = 1000
        with self.assertRaises(ValueError):
            fit_regression(features, self.target)

    def test_rejects_rank_deficient_training(self):
        """Dependent features cannot identify all regression slopes."""
        features = np.array([
            [20, 40, 1000],
            [21, 42, 1003],
            [22, 44, 1006],
            [23, 46, 1009],
            [24, 48, 1012],
        ], dtype=float)
        with self.assertRaises(ValueError):
            fit_regression(features, [400, 410, 420, 430, 440])


if __name__ == "__main__":
    unittest.main()
