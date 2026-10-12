"""Reusable cubic spline and regression models for CO2 reconstruction.

Requires NumPy and SciPy. CO2 inputs and predictions are in ppm.
Regression feature columns must be temperature (degrees Celsius),
humidity (percent), and pressure (mb), in that order.
"""

from dataclasses import dataclass

import numpy as np
from scipy.interpolate import CubicSpline


def cubic_spline_predict(observed_times, observed_values, query_times):
    """Estimate CO2 using a natural cubic spline.

    Parameters
    ----------
    observed_times : array-like, shape (n,)
        Strictly increasing observed timestamps in seconds, n >= 2.
        Provide only available observations, excluding hidden readings.
    observed_values : array-like, shape (n,)
        Observed CO2 concentrations in ppm.
    query_times : array-like, shape (m,)
        Timestamps in seconds within the observed time range.

    Returns
    -------
    numpy.ndarray, shape (m,)
        Estimated CO2 concentrations in ppm.

    Raises
    ------
    ValueError
        For invalid shapes, nonfinite inputs, unordered observation
        times, or queries outside the observed range.

    Notes
    -----
    Natural boundary conditions set the second derivative to zero
    at both ends of the observed context. Extrapolation is disabled.
    The spline can overshoot; predictions are not clipped.
    """
    times = np.asarray(observed_times, dtype=float)
    values = np.asarray(observed_values, dtype=float)
    queries = np.asarray(query_times, dtype=float)

    if times.ndim != 1 or values.ndim != 1 or queries.ndim != 1:
        raise ValueError("Times, values, and queries must be 1D arrays.")

    if len(times) < 2 or len(values) != len(times):
        raise ValueError("Provide at least two matching observations.")

    if not all(np.isfinite(a).all() for a in (times, values, queries)):
        raise ValueError("All inputs must contain finite numbers.")

    if np.any(np.diff(times) <= 0):
        raise ValueError("Observation times must be strictly increasing.")

    if np.any((queries < times[0]) | (queries > times[-1])):
        raise ValueError("Queries must lie within the observed range.")

    # Relative seconds avoid unnecessarily large Unix timestamp values.
    origin = times[0]
    spline = CubicSpline(
        times - origin,
        values,
        bc_type="natural",
        extrapolate=False,
    )
    return spline(queries - origin)


def _validate_features(features):
    """Convert features to a finite array with three columns."""
    features = np.asarray(features, dtype=float)

    if features.ndim != 2 or features.shape[1] != 3:
        raise ValueError(
            "Features must have three columns: "
            "temperature, humidity, pressure."
        )

    if not np.isfinite(features).all():
        raise ValueError("Features must contain finite numbers.")

    return features


@dataclass
class CO2Regression:
    """Fitted multiple linear regression model.

    feature_mean and feature_scale contain training means and standard
    deviations in the original feature units. coefficients contains
    the intercept followed by three slopes for standardized features.
    Coefficients and predictions have units of ppm.

    Create this model using fit_regression().
    """

    feature_mean: np.ndarray
    feature_scale: np.ndarray
    coefficients: np.ndarray

    def predict(self, features):
        """Predict CO2 in ppm from an (m, 3) feature array.

        Columns must be temperature (degrees Celsius), humidity
        (percent), and pressure (mb). These measurements must be
        available during the CO2 gap. Returns an array of length m.

        Raises ValueError for invalid shapes or nonfinite inputs.
        Prediction uses the stored training scaling without refitting.
        """
        features = _validate_features(features)
        scaled = (features - self.feature_mean) / self.feature_scale
        matrix = np.column_stack([np.ones(len(features)), scaled])
        return matrix @ self.coefficients


def fit_regression(training_features, training_co2):
    """Fit CO2 regression using only the supplied training observations.

    Parameters
    ----------
    training_features : array-like, shape (n, 3)
        Temperature (degrees Celsius), humidity (percent), and
        pressure (mb), in that order.
    training_co2 : array-like, shape (n,)
        Corresponding observed CO2 concentrations in ppm.

    Returns
    -------
    CO2Regression
        Model containing training scaling and least-squares coefficients.

    Raises
    ------
    ValueError
        For invalid shapes, nonfinite values, fewer than four rows,
        constant features, or a rank-deficient design matrix.

    Notes
    -----
    Scaling is calculated from training data only. The caller must
    exclude validation readings and hidden CO2 targets from training.
    Regression estimates associations, not causal relationships.
    """
    features = _validate_features(training_features)
    target = np.asarray(training_co2, dtype=float)

    if target.ndim != 1 or len(target) != len(features):
        raise ValueError("Provide one CO2 target per training row.")

    if len(features) < 4:
        raise ValueError("At least four training rows are required.")

    if not np.isfinite(target).all():
        raise ValueError("CO2 targets must contain finite numbers.")

    feature_mean = features.mean(axis=0)
    feature_scale = features.std(axis=0)

    if np.any(feature_scale == 0):
        raise ValueError("Training features must not be constant.")

    scaled = (features - feature_mean) / feature_scale
    matrix = np.column_stack([np.ones(len(features)), scaled])

    coefficients, _, rank, _ = np.linalg.lstsq(
        matrix, target, rcond=None
    )

    if rank != matrix.shape[1]:
        raise ValueError("Training design matrix must have full rank.")

    return CO2Regression(feature_mean, feature_scale, coefficients)
