"""Reproduce the four-method development comparison for CO₂ gaps.

Run from the repository root:
    python src/compare.py path/to/environment.zip

Optional arguments:
    --sensor-id 6012002000869
    --context-points 4
    --output co2_comparison_reproduced.csv

Input: an environmental sensor ZIP containing exactly one CSV.
Outputs: a printed comparison table and a CSV of aggregate error metrics.
The chosen output file is replaced if it already exists.

Regression trains on the first 50% of chronological observations.
Artificial gaps are evaluated in the following 25%. This is a
development comparison used for method selection, not an untouched
final validation set. The notebook contains separate runtime,
sensitivity and later-period robustness experiments.
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
    """Load and align environmental measurements by exact timestamp.

    Parameters
    ----------
    zip_path : str or pathlib.Path
        Environmental sensor ZIP containing exactly one CSV member.
        The CSV must use UTF-8, optionally with a byte-order mark,
        and contain "sensorid" and "jsondata" columns.
        Each selected JSON record must contain measurement entries
        with variable metadata and "time"/"value" pairs.
    sensor_id : str
        Exact sensor identifier to select from the CSV.

    Returns
    -------
    pandas.DataFrame
        Table sorted by ascending Unix timestamp in seconds, with index
        name "timestamp_seconds". Columns are "Carbon dioxide" (ppm),
        "Temperature" (degrees Celsius), "Humidity" (percent), and
        "Pressure" (mb). Every row contains all four measurements.

    Raises
    ------
    ValueError
        If the archive does not contain exactly one CSV, required
        columns are absent, selected timestamp/value entries are
        invalid or nonfinite, a required variable has no measurements,
        repeated timestamps contain conflicting values, or the four
        variables are not completely aligned.
    OSError
        If the archive cannot be opened or read.
    zipfile.BadZipFile
        If the supplied file is not a valid ZIP archive.
    json.JSONDecodeError
        If a selected row contains malformed JSON.
    TypeError
        If parsed JSON structures are incompatible with the expected
        iterable measurement structure.
    AttributeError
        If measurement entries lack the expected mapping interface.

    Notes
    -----
    Identical repeated timestamp/value pairs are collapsed. Different
    values at one timestamp cause rejection rather than arbitrary
    selection. Exact timestamp alignment is required; missing values
    are not filled, interpolated or silently discarded.

    Variables outside the four selected names and rows belonging to
    other sensors are ignored. Values are converted to floating-point
    numbers. Units are assumed from the Dataset 2 variable definitions;
    unit metadata and physical measurement ranges are not validated.

    Examples
    --------
    >>> table = load_sensor_table(
    ...     "environment.zip", "6012002000869"
    ... )  # doctest: +SKIP
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

                        # Collapse identical repeats while retaining
                        # conflicting values for explicit rejection.
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

    # Building columns on their timestamp union exposes any missing
    # alignment as NaN, which is rejected rather than silently filled.
    table = pd.DataFrame(clean).sort_index()
    table.index.name = "timestamp_seconds"

    if table.isna().any().any():
        raise ValueError("The four variables are not fully aligned.")

    return table


def compare_methods(table, context_points=4):
    """Compare four methods on independently simulated CO₂ gaps.

    Parameters
    ----------
    table : pandas.DataFrame
        Complete table in the format returned by load_sensor_table().
        Its index contains finite, strictly increasing Unix timestamps
        in seconds. Required columns contain finite CO₂ (ppm),
        temperature (degrees Celsius), humidity (percent), and pressure
        (mb). Sufficient rows and training variation are required.
    context_points : int, optional
        Positive number of observed readings on each side supplied to
        the natural cubic spline. Defaults to four. This setting also
        determines candidate-window eligibility and spacing.

    Returns
    -------
    pandas.DataFrame
        Twelve rows: four methods for each of 6, 18 and 36 hidden
        readings. Columns contain:
        "Hidden readings" — missing readings per simulated gap;
        "Gaps evaluated" — accepted windows for that gap size;
        "Method" — previous, linear, cubic_spline or regression;
        "MAE (ppm)" — pooled mean absolute reconstruction error;
        "RMSE (ppm)" — pooled root mean square reconstruction error;
        "Median boundary interval (min)" — median elapsed time between
        the observed readings immediately surrounding each gap.
        This function returns results without writing a file.

    Raises
    ------
    ValueError
        If context_points is invalid, data are nonnumeric or nonfinite,
        timestamps are not strictly increasing, regression training is
        unsuitable, predictions are nonfinite, or a gap size has no
        eligible windows.
    KeyError
        If a required measurement column is missing.
    TypeError
        If supplied objects do not support the required conversions.
    numpy.linalg.LinAlgError
        If the regression least-squares solver fails to converge.
    OverflowError
        If a timestamp is outside the supported datetime range.
    OSError
        If the platform cannot convert a timestamp.

    Notes
    -----
    Regression is fitted using only the first 50% of observations.
    Candidate gaps and their spline context lie within the following
    25%. The final 25% is not evaluated by this function.

    Candidate starts advance by gap_size + 2 * context_points.
    Hidden windows do not overlap within a gap size. Each window is
    treated as a separate missing-data event using the original observed
    context. Windows containing an adjacent interval above 30 minutes
    are skipped. Gap sizes count readings, not fixed durations.

    All four methods predict the same hidden targets within each gap
    size. Hidden CO₂ values enter scoring only, not reconstruction or
    training. Regression assumes temperature, humidity and pressure
    remain available during the CO₂ gap. Interpolation requires later
    observed CO₂, making this an offline reconstruction comparison.

    MAE and RMSE pool errors across all hidden readings for each method
    and gap size. These metrics assess agreement with recorded sensor
    values, not independently verified physical concentrations.
    Development results inform method selection.

    Changing context_points changes both spline context and evaluated
    windows. Use the notebook's fixed-window sensitivity experiment to
    isolate the effect of context size.

    Examples
    --------
    >>> table = load_sensor_table(
    ...     "environment.zip", "6012002000869"
    ... )  # doctest: +SKIP
    >>> results = compare_methods(table)  # doctest: +SKIP
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

    # Fit once using the earlier training segment; hidden evaluation
    # targets cannot influence the regression coefficients or scaling.
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

            # Avoid combining artificial missing readings with an
            # existing long interruption in the measurement sequence.
            if np.any(np.diff(window_times) > 1800):
                continue

            # Only observed readings outside the hidden interval
            # supply the spline context.
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

            # Hidden CO₂ enters scoring only, after predictions exist.
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
    """Run the command-line comparison and save aggregate results.

    Parameters
    ----------
    None
        Reads command-line arguments: required zip_path, optional
        --sensor-id, --context-points, and --output.

    Returns
    -------
    None
        Writes the comparison CSV without a row index and prints the
        sensor ID, aligned observation count, comparison segment,
        rounded result table and output path.

    Raises
    ------
    SystemExit
        If command-line arguments are invalid or help is requested.
    OSError
        If input files cannot be read, output directories cannot be
        created, or the CSV cannot be written.
    ValueError
        If loading, alignment, training or comparison validation fails.

    Notes
    -----
    Defaults are sensor "6012002000869", four spline observations per
    side, and output "co2_method_comparison.csv". Parent directories are
    created as needed. An existing output file is replaced.

    Exceptions from load_sensor_table() and compare_methods() propagate
    to the caller. No plots, runtime measurements or later-period
    robustness results are generated by this command.

    Examples
    --------
    From the repository root, run:
        python src/compare.py path/to/environment.zip
    To preserve the existing comparison CSV, specify another output:
        python src/compare.py path/to/environment.zip --output new.csv
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip_path", help="Environmental sensor ZIP")
    parser.add_argument("--sensor-id", default="6012002000869")
    parser.add_argument(
        "--output",
        default="co2_method_comparison.csv",
        help="Output CSV path; an existing file will be replaced.",
    )
    parser.add_argument(
        "--context-points",
        type=int,
        default=4,
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
