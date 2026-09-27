"""Audit CO2 readings in the Dataset 2 environmental sensor ZIP."""

import csv
import io
import json
import sys
import zipfile
from collections import Counter


def audit(zip_path, sensor_id="6012002000869"):
    rows_for_sensor = 0
    readings = {}

    with zipfile.ZipFile(zip_path) as archive:
        csv_name = next(
            name for name in archive.namelist()
            if name.lower().endswith(".csv")
        )

        with archive.open(csv_name) as raw_file:
            text_file = io.TextIOWrapper(raw_file, encoding="utf-8-sig")
            for row in csv.DictReader(text_file):
                if row["sensorid"] != sensor_id:
                    continue

                rows_for_sensor += 1
                for measurement in json.loads(row["jsondata"]):
                    variable = measurement.get("variable", {})
                    if variable.get("name") != "Carbon dioxide":
                        continue

                    for item in measurement.get("values", []):
                        timestamp = item.get("time")
                        value = item.get("value")
                        if timestamp is not None and value is not None:
                            readings[(timestamp, value)] = None

    timestamps = [timestamp for timestamp, _ in readings]
    timestamp_counts = Counter(timestamps)

    print(f"Sensor ID: {sensor_id}")
    print(f"CSV rows for sensor: {rows_for_sensor}")
    print(f"Distinct timestamp/value pairs: {len(readings)}")
    print(f"Distinct measurement timestamps: {len(timestamp_counts)}")
    print(f"Timestamps with conflicting CO2 values: "
          f"{sum(count > 1 for count in timestamp_counts.values())}")
    print("Unit: ppm")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python src/audit.py path/to/environment.zip")
    audit(sys.argv[1])
