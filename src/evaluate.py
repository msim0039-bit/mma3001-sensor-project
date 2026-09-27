"""Evaluate short-gap CO2 reconstruction on Dataset 2.

Run: python src/evaluate.py path/to/5EnvSensor_MayToDec2024_180kRows.zip
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
    """Return distinct CO2 readings ordered by Unix timestamp."""
    readings = {}
    with zipfile.ZipFile(zip_path) as archive:
        csv_name = next(
            name for name in archive.namelist() if name.lower().endswith(".csv")
        )
        with archive.open(csv_name) as raw_file:
            rows = csv.DictReader(io.TextIOWrapper(raw_file, encoding="utf-8-sig"))
            for row in rows:
                if row["sensorid"] != sensor_id:
                    continue
                for measurement in json.loads(row["jsondata"]):
                    if measurement.get("variable", {}).get("name") != "Carbon dioxide":
                        continue
                    for item in measurement.get("values", []):
                        readings[int(item["time"])] = float(item["value"])

    if not readings:
        raise ValueError(f"No CO2 readings found for sensor {sensor_id}")
    times = sorted(readings)
    return times, [readings[t] for t in times]


def evaluate(times, co2):
    """Hide disjoint windows in the middle 25% and score both methods."""
    evaluation_start = int(0.50 * len(co2))
    evaluation_end = int(0.75 * len(co2))

    def as_datetime(seconds):
        return datetime.fromtimestamp(seconds, timezone.utc)

    for gap_size in (6, 18, 36):
        errors = {"previous": [], "linear": []}
        runtimes = {"previous": 0.0, "linear": 0.0}
        gap_count = 0

        for start in range(
            evaluation_start + 1, evaluation_end - gap_size, gap_size + 8
        ):
            window_times = times[start - 1:start + gap_size + 1]
            if any(
                b - a > 30 * 60
                for a, b in zip(window_times, window_times[1:])
            ):
                continue

            hidden_times = [
                as_datetime(t) for t in times[start:start + gap_size]
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
        "zip_path", help="Path to the original environmental sensor ZIP"
    )
    args = parser.parse_args()
    timestamps, values = load_readings(args.zip_path)
    print(f"Loaded {len(values)} distinct CO2 readings")
    evaluate(timestamps, values)
