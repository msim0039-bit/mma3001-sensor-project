"""Run the earlier two-method CO₂ gap-reconstruction evaluation.

Run from the repository root:
    python src/evaluate.py path/to/environment.zip

Compares previous-value reconstruction and linear interpolation on
artificial gaps in the chronological 50%–75% segment.

This module preserves the earlier experiment. Use compare.py for the
current four-method comparison and stricter data validation.
"""

import argparse
import csv
import io
import json
import math
import time
import zipfile
from datetime import datetime, timezone

from reconstruct import reconstruct_gap


def load_readings(zip_path, sensor_id="6012002000869"):
    """Load timestamp-ordered CO₂ readings for one sensor.

    Parameters
    ----------
    zip_path : str or pathlib.Path
        Environmental sensor ZIP containing a UTF-8 CSV, optionally
        with a byte-order mark. The first member ending in ".csv" is
        read. Required CSV columns are "sensorid" and "jsondata".
        JSON measurement entries must provide variable metadata and
        values containing "time" and "value" fields.
    sensor_id : str, optional
        Exact sensor identifier to select. Defaults to "6012002000869".

    Returns
    -------
    times : list of int
        Distinct Unix timestamps in seconds, sorted in ascending order.
        Timestamp inputs are converted using int().
    co2 : list of float
        Corresponding CO₂ concentrations in ppm. Each position matches
        the same position in times.

    Raises
    ------
    OSError
        If the archive cannot be opened or read.
    zipfile.BadZipFile
        If the supplied file is not a valid ZIP archive.
    StopIteration
        If the archive contains no CSV member.
    KeyError
        If required CSV columns or timestamp/value fields are missing.
    json.JSONDecodeError
        If selected JSON records are malformed.
    ValueError
        If no CO₂ readings are found or numeric conversion fails.
    TypeError
        If timestamp/value types are incompatible with conversion or
        parsed structures do not match the expected format.
    AttributeError
        If measurement entries lack the expected mapping interface.
    OverflowError
        If a timestamp cannot be converted to an integer.

    Notes
    -----
    Repeated timestamps overwrite earlier values; the last encountered
    value is retained. Conflicting values are not detected by this
    loader. Conversion to int truncates fractional timestamp values.

    Missing fields are not silently skipped. Finite concentrations,
    physical ranges and variable units are not explicitly checked.
    Use the stricter loader in compare.py for the current analysis.

    Examples
    --------
    >>> times, co2 = load_readings("environment.zip")  # doctest: +SKIP
    """
    readings = {}

    with zipfile.ZipFile(zip_path) as archive:
        csv_name = next(
            name for name in archive.namelist()
            if name.lower().endswith(".csv")
        )

        with archive.open(csv_name) as raw_file:
            rows = csv.DictReader(
                io.TextIOWrapper(raw_file, encoding="utf-8-sig")
            )

            for row in rows:
                if row["sensorid"] != sensor_id:
                    continue

                for measurement in json.loads(row["jsondata"]):
                    if (
                        measurement.get("variable", {}).get("name")
                        != "Carbon dioxide"
                    ):
                        continue

                    for item in measurement.get("values", []):
                        # Preserve the original loader's last-value rule.
                        # Conflict detection belongs to the audit and
                        # the stricter current comparison loader.
                        readings[int(item["time"])] = float(item["value"])

    if not readings:
        raise ValueError(f"No CO2 readings found for sensor {sensor_id}")

    times = sorted(readings)
    return times, [readings[t] for t in times]


def evaluate(times, co2):
    """Print accuracy and accumulated runtime for two gap methods.

    Parameters
    ----------
    times : list of int or float
        Finite, strictly increasing Unix timestamps in seconds.
        Must correspond one-to-one with co2.
    co2 : list of float
        Finite observed CO₂ concentrations in ppm. Must have the same
        length as times. The caller must validate alignment, ordering
        and numeric suitability before calling this function.

    Returns
    -------
    None
        Prints the number of evaluated gaps for each gap size, followed
        by mean absolute error (MAE), root mean square error (RMSE),
        and accumulated method runtime. Errors are in ppm; runtime
        is in seconds. No result file is written.

    Raises
    ------
    ValueError
        If timestamp conversion or reconstruction fails, including
        invalid boundary ordering or target times outside the gap.
    TypeError
        If inputs do not support the required numeric operations.
    IndexError
        If misaligned inputs cause an unavailable position to be read.
    OverflowError
        If a timestamp is outside the datetime conversion range.
    OSError
        If the platform cannot convert a supplied Unix timestamp.

    Notes
    -----
    Uses the chronological 50%–75% segment and gap sizes of 6, 18 and
    36 hidden readings. Candidate starts advance by gap_size + 8,
    preventing overlap between hidden windows for a given gap size.
    Different gap sizes need not use the same windows.

    A window is skipped if an adjacent timestamp interval exceeds
    30 minutes. Gap sizes count readings, not fixed elapsed durations.

    Both methods reconstruct the same hidden readings. Hidden CO₂
    values are used only for scoring. MAE and RMSE pool errors across
    all evaluated readings within each gap size.

    Runtime includes boundary datetime conversion and reconstruction,
    but excludes data loading, hidden-time preparation and scoring.
    It is a single accumulated timing, without repeated batches or a
    warm-up. Use the notebook benchmark for the current repeated timing
    experiment.

    Input validation is not comprehensive. If no eligible windows exist,
    a zero-gap count is printed without accuracy or runtime lines.
    Errors measure agreement with sensor readings, not independently
    verified physical concentrations.

    Examples
    --------
    >>> times, co2 = load_readings("environment.zip")  # doctest: +SKIP
    >>> evaluate(times, co2)  # doctest: +SKIP
    """
    evaluation_start = int(0.50 * len(co2))
    evaluation_end = int(0.75 * len(co2))

    def as_datetime(seconds):
        """Convert Unix seconds to a timezone-aware UTC datetime.

        Parameters
        ----------
        seconds : int or float
            Unix timestamp in seconds within the supported datetime range.

        Returns
        -------
        datetime
            Timezone-aware timestamp expressed in UTC.

        Raises
        ------
        TypeError
            If seconds is not compatible with timestamp conversion.
        ValueError
            If the timestamp is invalid or outside the supported range.
        OverflowError
            If the platform cannot represent the timestamp.
        OSError
            If the platform timestamp conversion fails.
        """
        return datetime.fromtimestamp(seconds, timezone.utc)

    for gap_size in (6, 18, 36):
        errors = {"previous": [], "linear": []}
        runtimes = {"previous": 0.0, "linear": 0.0}
        gap_count = 0

        for start in range(
            evaluation_start + 1,
            evaluation_end - gap_size,
            gap_size + 8,
        ):
            window_times = times[start - 1:start + gap_size + 1]

            # Avoid combining an artificial gap with an existing long
            # interruption in the recorded measurement sequence.
            if any(
                b - a > 30 * 60
                for a, b in zip(window_times, window_times[1:])
            ):
                continue

            hidden_times = [
                as_datetime(t)
                for t in times[start:start + gap_size]
            ]
            actual = co2[start:start + gap_size]

            for method in ("previous", "linear"):
                begin = time.perf_counter()
                predicted = reconstruct_gap(
                    as_datetime(times[start - 1]),
                    co2[start - 1],
                    hidden_times,
                    as_datetime(times[start + gap_size]),
                    co2[start + gap_size],
                    method,
                )
                runtimes[method] += time.perf_counter() - begin

                # Keep hidden observations separate from prediction
                # inputs and use them only to calculate errors.
                errors[method].extend(
                    a - p for a, p in zip(actual, predicted)
                )

            gap_count += 1

        print(f"\n{gap_size} hidden readings | {gap_count} tested gaps")

        for method in ("previous", "linear"):
            error = errors[method]
            if error:
                mae = sum(abs(e) for e in error) / len(error)
                rmse = math.sqrt(
                    sum(e * e for e in error) / len(error)
                )
                print(
                    f"{method}: MAE {mae:.2f} ppm | "
                    f"RMSE {rmse:.2f} ppm | "
                    f"method time {runtimes[method]:.4f} s"
                )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "zip_path",
        help="Path to the original environmental sensor ZIP",
    )
    args = parser.parse_args()
    timestamps, values = load_readings(args.zip_path)
    print(f"Loaded {len(values)} distinct CO2 readings")
    evaluate(timestamps, values)
