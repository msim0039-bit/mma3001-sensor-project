"""Reusable natural cubic spline and CO₂ regression models.

Requires NumPy and SciPy. CO₂ observations and predictions use ppm.
Regression feature columns are temperature (degrees Celsius),
humidity (percent), and pressure (mb), in that order.

The caller selects observed context and training data. Hidden CO₂
targets must not enter spline context or regression training.
"""

from dataclasses import dataclass

import numpy as np
from scipy.interpolate import CubicSpline


def cubic_spline_predict(observed_times, observed_values, query_times):
    """Estimate CO₂ using a natural cubic spline.

    Parameters
    ----------
    observed_times : array-like of float, shape (n,)
        Finite, strictly increasing timestamps in seconds, with n >= 2.
        Use a consistent time basis for observations and queries.
        Supply only available observations, excluding hidden readings.
    observed_values : array-like of float, shape (n,)
        Finite observed CO₂ concentrations in ppm, one per timestamp.
    query_times : array-like of float, shape (m,)
        Finite timestamps in seconds within the inclusive observed
        range. Queries may be unsorted or repeated. An empty array
        produces an empty prediction array.

    Returns
    -------
    numpy.ndarray of float, shape (m,)
        Estimated CO₂ concentrations in ppm, preserving query order.

    Raises
    ------
    ValueError
        If inputs cannot be converted to numeric arrays, shapes are
        invalid, fewer than two observations are supplied, inputs are
        nonfinite, observation times are not strictly increasing, or
        queries fall outside the observed range.
    TypeError
        If input elements have types incompatible with float conversion.

    Notes
    -----
    Natural boundary conditions set the second derivative to zero at
    both ends of the supplied observed context. Extrapolation is disabled.
    The number of context observations is chosen by the caller.

    The method assumes the observed context supports a smooth curve.
    It can introduce curvature and overshoot across missing intervals.
    Predictions are not clipped or checked against physical limits.
    Relative seconds reduce the magnitude of timestamps used internally;
    they do not recover precision already lost in supplied timestamps.

    Examples
    --------
    >>> cubic_spline_predict([0, 10, 20], [400, 410, 420], [5, 15])
    array([405., 415.])
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

    # Reduce timestamp magnitude while preserving elapsed-time intervals.
    origin = times[0]
    spline = CubicSpline(
        times - origin,
        values,
        bc_type="natural",
        extrapolate=False,
    )
    return spline(queries - origin)


def _validate_features(features):
    """Convert environmental measurements to a finite feature matrix.

    Parameters
    ----------
    features : array-like of float, shape (m, 3)
        Temperature (degrees Celsius), humidity (percent), and pressure
        (mb), in that order. An array of shape (0, 3) is accepted.

    Returns
    -------
    numpy.ndarray of float, shape (m, 3)
        Numeric feature matrix. No physical-range checks are applied.

    Raises
    ------
    ValueError
        If conversion fails, the array does not have three columns,
        or any element is nonfinite.
    TypeError
        If input elements have types incompatible with float conversion.
    """
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
    """Store a fitted multiple linear regression model for CO₂.

    Parameters
    ----------
    feature_mean : numpy.ndarray, shape (3,)
        Training means in the original feature units: degrees Celsius,
        percent humidity, and mb pressure.
    feature_scale : numpy.ndarray, shape (3,)
        Training population standard deviations in the same units.
        Values must be positive.
    coefficients : numpy.ndarray, shape (4,)
        Intercept followed by slopes for standardized temperature,
        humidity and pressure. The intercept is in ppm; slopes represent
        ppm per unit change in the dimensionless standardized features.

    Notes
    -----
    Create instances through fit_regression(), which checks training
    data and constructs compatible arrays. Direct construction does not
    validate these stored parameters.

    The model estimates linear associations between environmental
    measurements and CO₂. These associations are not causal, and may
    change between time periods or buildings.
    """

    feature_mean: np.ndarray
    feature_scale: np.ndarray
    coefficients: np.ndarray

    def predict(self, features):
        """Predict CO₂ using fixed training coefficients and scaling.

        Parameters
        ----------
        features : array-like of float, shape (m, 3)
            Finite temperature (degrees Celsius), humidity (percent),
            and pressure (mb), in that order. These measurements must
            be available at the times of the missing CO₂ readings.

        Returns
        -------
        numpy.ndarray of float, shape (m,)
            Predicted CO₂ concentrations in ppm, preserving row order.
            An input of shape (0, 3) produces an empty array.

        Raises
        ------
        ValueError
            If features cannot be converted to numeric values, have an
            invalid shape, or contain nonfinite values.
        TypeError
            If input elements are incompatible with float conversion.

        Notes
        -----
        Uses stored training statistics without refitting them on
        prediction data. Inputs outside the training range are accepted,
        but predictions there may be unreliable. Outputs are not clipped
        or checked against physical concentration limits.

        Examples
        --------
        >>> model = CO2Regression(
        ...     np.array([20.0, 40.0, 1000.0]),
        ...     np.array([1.0, 1.0, 1.0]),
        ...     np.array([400.0, 2.0, 0.5, -0.1]),
        ... )
        >>> model.predict([[21.0, 44.0, 1002.0]])
        array([403.8])
        """
        features = _validate_features(features)

        # Reuse training scaling so predictions do not depend on other
        # rows supplied in the same prediction batch.
        scaled = (features - self.feature_mean) / self.feature_scale
        matrix = np.column_stack([np.ones(len(features)), scaled])
        return matrix @ self.coefficients


def fit_regression(training_features, training_co2):
    """Fit CO₂ regression using supplied training observations.

    Parameters
    ----------
    training_features : array-like of float, shape (n, 3)
        Finite temperature (degrees Celsius), humidity (percent), and
        pressure (mb), in that order. Requires n >= 4, nonconstant
        features, and a full-rank design matrix including the intercept.
    training_co2 : array-like of float, shape (n,)
        Finite observed CO₂ concentrations in ppm corresponding to
        the feature rows.

    Returns
    -------
    CO2Regression
        Model containing training means, population standard deviations
        and least-squares coefficients for subsequent prediction.

    Raises
    ------
    ValueError
        If conversion fails, shapes are invalid, values are nonfinite,
        fewer than four rows are supplied, a feature is constant, or
        the design matrix is rank deficient.
    TypeError
        If input elements have types incompatible with float conversion.
    numpy.linalg.LinAlgError
        If the least-squares solver fails to converge.

    Notes
    -----
    Fits an intercept and three slopes by minimizing the sum of squared
    CO₂ residuals. Scaling is calculated from training data only.
    The caller must exclude validation readings and hidden CO₂ targets
    from training.

    Full rank permits identification of the coefficients; it does not
    guarantee good conditioning or accurate predictions. Finite inputs
    are checked, but physical ranges and extreme-value overflow are
    not explicitly checked. Regression estimates associations rather
    than causal relationships.

    Examples
    --------
    >>> features = np.array([
    ...     [20, 40, 1000],
    ...     [22, 40, 1000],
    ...     [20, 50, 1000],
    ...     [20, 40, 1010],
    ... ], dtype=float)
    >>> targets = np.array([400, 404, 405, 399], dtype=float)
    >>> model = fit_regression(features, targets)
    >>> np.allclose(model.predict([[21, 44, 1002]]), [403.8])
    True
    """
    features = _validate_features(training_features)
    target = np.asarray(training_co2, dtype=float)

    if target.ndim != 1 or len(target) != len(features):
        raise ValueError("Provide one CO2 target per training row.")

    if len(features) < 4:
        raise ValueError("At least four training rows are required.")

    if not np.isfinite(target).all():
        raise ValueError("CO2 targets must contain finite numbers.")

    # Training-only statistics prevent prediction data influencing fitting.
    feature_mean = features.mean(axis=0)
    feature_scale = features.std(axis=0)

    if np.any(feature_scale == 0):
        raise ValueError("Training features must not be constant.")

    scaled = (features - feature_mean) / feature_scale

    # A column of ones permits a nonzero intercept.
    matrix = np.column_stack([np.ones(len(features)), scaled])

    # Solve least squares directly rather than explicitly inverting a matrix.
    coefficients, _, rank, _ = np.linalg.lstsq(
        matrix, target, rcond=None
    )

    if rank != matrix.shape[1]:
        raise ValueError("Training design matrix must have full rank.")

    return CO2Regression(feature_mean, feature_scale, coefficients)
