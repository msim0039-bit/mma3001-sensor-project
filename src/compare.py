"""Reproduce the four-method development comparison for CO2 gaps.

Usage:
    python src/compare.py path/to/environment.zip

Inputs: environmental sensor ZIP containing one CSV; sensor ID.
Output: comparison table and co2_method_comparison.csv.

Regression trains on the first 50% of chronological observations.
Artificial gaps are evaluated in the following 25%. This is a
development comparison, not an untouched final validation set.
"""

import argparse
import csv
import io
import json
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from models import cubic_spline_predict, fit_regression
from reconstruct import reconstruct_gap


VARIABLES = [
    "Carbon dioxide",
    "Temperature",
    "Humidity",
    "Pressure",
]
METHODS = ["previous", "linear", "cubic_spline", "regression"]


def load_sensor_table(zip_path, sensor_id):
    """Load and align four variables by exact Unix timestamp.

    Returns a sorted DataFrame indexed by timestamp in seconds.
    Columns contain CO2 (ppm), temperature (degrees Celsius),
    humidity (percent), and pressure (mb).

    Identical repeated measurements are collapsed. Conflicting values,
    invalid measurements, absent variables, or incomplete alignment
    raise ValueError rather than being silently filled or discarded.
    The archive must contain exactly one CSV.
    """
    readings = {name: defaultdict(set) for name in VARIABLES}

    with zipfile.ZipFile(zip_path) as archive:
        csv_names = [
            name for name in archive.namelist()
            if name.lower().endswith(".csv")
        ]
        if len(csv_names) != 1:
            raise ValueError("The ZIP must contain exactly one CSV.")

        with archive.open(csv_names[0]) as raw_file:
            text_file = io.TextIOWrapper(
                raw_file, encoding="utf-8-sig"
            )
            reader = csv.DictReader(text_file)

            required = {"sensorid", "jsondata"}
            if not required.issubset(reader.fieldnames or []):
                raise ValueError("CSV requires sensorid and jsondata.")

            for row in reader:
                if row["sensorid"] != sensor_id:
                    continue

                for measurement in json.loads(row["jsondata"]):
                    name = measurement.get("variable", {}).get("name")
                    if name not in readings:
                        continue

                    for item in measurement.get("values", []):
                        try:
                            timestamp = float(item["time"])
                            value = float(item["value"])
                        except (KeyError, TypeError, ValueError) as error:
                            raise ValueError(
                                f"Invalid measurement for {name}."
                            ) from error

                        if not np.isfinite([timestamp, value]).all():
                            raise ValueError(
                                f"Nonfinite measurement for {name}."
                            )
                        readings[name][timestamp].add(value)

    clean = {}
    for name, measurements in readings.items():
        if not measurements:
            raise ValueError(f"No measurements found for {name}.")

        if any(len(values) != 1 for values in measurements.values()):
            raise ValueError(f"Conflicting values found for {name}.")

        clean[name] = {
            timestamp: next(iter(values))
            for timestamp, values in measurements.items()
        }

    table = pd.DataFrame(clean).sort_index()
    table.index.name = "timestamp_seconds"

    if table.isna().any().any():
        raise ValueError("The four variables are not fully aligned.")

    return table


def compare_methods(table, context_points=4):
    """Evaluate independently simulated gaps of 6, 18 and 36 readings.

    Parameters
    ----------
    table : pandas.DataFrame
        Complete, chronological table returned by load_sensor_table.
    context_points : int
        Number of observed points on each side supplied to the spline.
        Defaults to four, matching the notebook comparison.

    Returns
    -------
    pandas.DataFrame
        Gap counts, MAE and RMSE in ppm, and median elapsed time
        between the surrounding observations in minutes.

    Notes
    -----
    All methods use the same hidden targets. Hidden CO2 readings are
    excluded from reconstruction inputs. Regression assumes that
    temperature, humidity and pressure remain available during gaps.
    Windows with an adjacent interval above 30 minutes are skipped.
    Each gap is treated as a separate missing-data event.
    """
    if not isinstance(context_points, int) or context_points < 1:
        raise ValueError("context_points must be a positive integer.")

    times = table.index.to_numpy(dtype=float)
    co2 = table["Carbon dioxide"].to_numpy(dtype=float)
    features = table[VARIABLES[1:]].to_numpy(dtype=float)

    if not np.isfinite(times).all() or not np.isfinite(co2).all():
        raise ValueError("Timestamps and CO2 must be finite.")
    if not np.isfinite(features).all():
        raise ValueError("Features must be finite.")
    if np.any(np.diff(times) <= 0):
        raise ValueError("Timestamps must be strictly increasing.")

    training_end = int(0.50 * len(table))
    comparison_end = int(0.75 * len(table))

    model = fit_regression(
        features[:training_end], co2[:training_end]
    )
    results = []

    for gap_size in (6, 18, 36):
        errors = {method: [] for method in METHODS}
        durations = []
        gap_count = 0

        first_start = training_end + context_points
        last_start = comparison_end - gap_size - context_points
        step = gap_size + 2 * context_points

        for start in range(first_start, last_start + 1, step):
            stop = start + gap_size
            window_times = times[
                start - context_points:stop + context_points
            ]
            if np.any(np.diff(window_times) > 1800):
                continue

            context_indices = np.concatenate([
                np.arange(start - context_points, start),
                np.arange(stop, stop + context_points),
            ])
            hidden_times = times[start:stop]
            actual = co2[start:stop]

            left_time = datetime.fromtimestamp(
                times[start - 1], tz=timezone.utc
            )
            right_time = datetime.fromtimestamp(
                times[stop], tz=timezone.utc
            )
            missing_times = [
                datetime.fromtimestamp(t, tz=timezone.utc)
                for t in hidden_times
            ]

            predictions = {}
            for method in ("previous", "linear"):
                predictions[method] = reconstruct_gap(
                    left_time,
                    co2[start - 1],
                    missing_times,
                    right_time,
                    co2[stop],
                    method=method,
                )

            predictions["cubic_spline"] = cubic_spline_predict(
                times[context_indices],
                co2[context_indices],
                hidden_times,
            )
            predictions["regression"] = model.predict(
                features[start:stop]
            )

            for method, predicted in predictions.items():
                predicted = np.asarray(predicted, dtype=float)
                if not np.isfinite(predicted).all():
                    raise ValueError(f"Nonfinite {method} prediction.")
                errors[method].extend(predicted - actual)

            durations.append(
                (times[stop] - times[start - 1]) / 60
            )
            gap_count += 1

        if gap_count == 0:
            raise ValueError(
                f"No eligible windows for gap size {gap_size}."
            )

        for method in METHODS:
            error = np.asarray(errors[method])
            results.append({
                "Hidden readings": gap_size,
                "Gaps evaluated": gap_count,
                "Method": method,
                "MAE (ppm)": np.mean(np.abs(error)),
                "RMSE (ppm)": np.sqrt(np.mean(error ** 2)),
                "Median boundary interval (min)": np.median(durations),
            })

    return pd.DataFrame(results)


def main():
    """Read CLI arguments, run the comparison, and save its CSV."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip_path", help="Environmental sensor ZIP")
    parser.add_argument("--sensor-id", default="6012002000869")
    parser.add_argument(
        "--output", default="co2_method_comparison.csv",
        help="Output CSV path; an existing file will be replaced.",
    )
    parser.add_argument(
        "--context-points", type=int, default=4,
        help="Observed points per side supplied to the spline.",
    )
    args = parser.parse_args()

    table = load_sensor_table(args.zip_path, args.sensor_id)
    results = compare_methods(table, args.context_points)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(output_path, index=False)

    print(f"Sensor: {args.sensor_id}")
    print(f"Aligned observations: {len(table)}")
    print("Development comparison: chronological 50% to 75% segment")
    print(results.round(2).to_string(index=False))
    print(f"\nSaved: {output_path}")


if __name__ == "__main__":
    main()
