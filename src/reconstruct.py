"""Methods for estimating missing CO2 sensor readings."""

from datetime import datetime


def reconstruct_gap(
    left_time: datetime,
    left_value: float,
    missing_times: list[datetime],
    right_time: datetime,
    right_value: float,
    method: str = "linear",
) -> list[float]:
    """Estimate readings between two observed sensor measurements.

    ``previous`` carries the last observed value forward.
    ``linear`` uses elapsed time to interpolate between both observations.
    """
    if left_time >= right_time:
        raise ValueError("The left observation must precede the right observation.")

    if any(not left_time < time < right_time for time in missing_times):
        raise ValueError("Every missing time must lie between the observations.")

    if method == "previous":
        return [float(left_value) for _ in missing_times]

    if method == "linear":
        total_seconds = (right_time - left_time).total_seconds()
        return [
            float(left_value)
            + (float(right_value) - float(left_value))
            * (time - left_time).total_seconds()
            / total_seconds
            for time in missing_times
        ]

    raise ValueError(f"Unknown method: {method}")
