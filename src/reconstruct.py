"""Reconstruct missing CO₂ readings between observed measurements.

Provides a previous-value baseline and elapsed-time linear interpolation.
Outputs are estimated CO₂ concentrations in parts per million (ppm).
"""

from datetime import datetime


def reconstruct_gap(
    left_time: datetime,
    left_value: float,
    missing_times: list[datetime],
    right_time: datetime,
    right_value: float,
    method: str = "linear",
) -> list[float]:
    """Estimate CO₂ readings inside a gap bounded by observations.

    Parameters
    ----------
    left_time : datetime
        Timestamp of the observation before the gap. Must precede
        right_time.
    left_value : float
        Observed CO₂ concentration before the gap, in ppm.
        Must be convertible to float.
    missing_times : list of datetime
        Timestamps at which estimates are required. Each must lie
        strictly between left_time and right_time. Estimates preserve
        the supplied order; timestamps need not be sorted or unique.
        An empty list returns an empty list for a supported method.
    right_time : datetime
        Timestamp of the observation after the gap.
    right_value : float
        Observed CO₂ concentration after the gap, in ppm.
        Must be convertible to float for the linear method.
        The previous-value method does not use this concentration.
    method : {"linear", "previous"}, optional
        Reconstruction method. Defaults to "linear".
        "previous" repeats left_value.
        "linear" interpolates between the two observations using
        elapsed time rather than measurement position.

    Returns
    -------
    list of float
        Estimated CO₂ concentrations in ppm, one per missing timestamp,
        in the same order as missing_times.

    Raises
    ------
    ValueError
        If the boundary timestamps are not strictly increasing, a
        missing timestamp is outside the open interval, the method is
        unsupported, or a required concentration cannot be converted
        to float.
    TypeError
        If timestamps cannot be compared or subtracted, missing_times
        is not iterable, or a required concentration has an incompatible
        type. Mixing timezone-aware and timezone-naive datetimes is
        unsupported.

    Notes
    -----
    Use compatible timestamps on a consistent time basis; UTC is used
    in the project workflow. Concentrations should be finite numbers
    in ppm. This function does not explicitly reject NaN, infinity or
    physically implausible concentrations; validate observations before
    calling it.

    Linear interpolation assumes a straight-line change across the gap.
    The previous-value baseline assumes concentration remains constant.
    Neither method recovers unobserved peaks or establishes physical
    measurement accuracy.

    Both methods require a later boundary timestamp in this interface.
    Linear interpolation also requires its observed concentration, so
    it is intended for offline reconstruction after that observation
    becomes available. Neither method uses hidden CO₂ readings.

    Examples
    --------
    >>> from datetime import timedelta
    >>> left = datetime(2024, 1, 1, 12, 0)
    >>> right = left + timedelta(minutes=30)
    >>> targets = [
    ...     left + timedelta(minutes=10),
    ...     left + timedelta(minutes=20),
    ... ]
    >>> reconstruct_gap(left, 400, targets, right, 430, "linear")
    [410.0, 420.0]
    >>> reconstruct_gap(left, 400, targets, right, 430, "previous")
    [400.0, 400.0]
    """
    if left_time >= right_time:
        raise ValueError(
            "The left observation must precede the right observation."
        )

    # Strictly internal target times prevent extrapolation and avoid
    # treating observed boundary readings as missing measurements.
    if any(not left_time < time < right_time for time in missing_times):
        raise ValueError(
            "Every missing time must lie between the observations."
        )

    if method == "previous":
        return [float(left_value) for _ in missing_times]

    if method == "linear":
        total_seconds = (right_time - left_time).total_seconds()

        # Elapsed-time weights accommodate uneven measurement intervals.
        return [
            float(left_value)
            + (float(right_value) - float(left_value))
            * (time - left_time).total_seconds()
            / total_seconds
            for time in missing_times
        ]

    raise ValueError(f"Unknown method: {method}")
