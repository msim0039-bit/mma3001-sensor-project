"""Audit repeated CO₂ records in the Dataset 2 environmental sensor ZIP.

Run from the repository root:
    python src/audit.py path/to/environment.zip

The audit reports record counts for one sensor. It does not reconstruct
missing readings or establish the physical accuracy of the measurements.
"""

import csv
import io
import json
import sys
import zipfile
from collections import Counter


def audit(zip_path, sensor_id="6012002000869"):
    """Print counts of repeated and conflicting CO₂ measurements.

    Parameters
    ----------
    zip_path : str or pathlib.Path
        Path to the environmental sensor ZIP. The first archive member
        whose name ends in ".csv" is read. The CSV must contain "sensorid"
        and "jsondata" columns and use UTF-8 encoding, optionally with a
        byte-order mark.
    sensor_id : str, optional
        Exact sensor identifier to select. Defaults to "6012002000869".
        Each selected row's "jsondata" must contain a JSON list of
        measurements with variable metadata and timestamp/value entries.
        CO₂ values are interpreted as parts per million (ppm); timestamps
        are compared as supplied, without conversion.

    Returns
    -------
    None
        Prints the selected sensor ID, matching CSV row count, distinct
        timestamp/value pair count, distinct timestamp count, number of
        timestamps containing different CO₂ values, and expected unit.

    Raises
    ------
    OSError
        If the ZIP cannot be opened or read.
    zipfile.BadZipFile
        If the supplied file is not a valid ZIP archive.
    StopIteration
        If the archive contains no CSV member.
    KeyError
        If a required CSV column is missing.
    json.JSONDecodeError
        If a selected row contains malformed JSON.
    TypeError
        If parsed measurement structures are incompatible with the
        expected format or timestamps/values cannot be dictionary keys.
    AttributeError
        If measurement entries do not provide the expected mapping fields.

    Notes
    -----
    Entries with a missing or null timestamp or value are skipped.
    Other values are counted as supplied: this audit does not check
    numeric validity, finite values, timestamp order, or physical ranges.
    If the selected sensor has no usable CO₂ records, counts are zero.

    Identical timestamp/value pairs are counted once. Different values
    at one timestamp are retained so conflicts remain visible.
    Use the stricter loader in compare.py before numerical analysis.

    Examples
    --------
    >>> audit("environment.zip")  # doctest: +SKIP
    """
    rows_for_sensor = 0
    readings = {}

    with zipfile.ZipFile(zip_path) as archive:
        # Use the first CSV member, matching the original audit workflow.
        csv_name = next(
            name for name in archive.namelist()
            if name.lower().endswith(".csv")
        )

        with archive.open(csv_name) as raw_file:
            # Accept the optional byte-order mark in the supplied CSV.
            text_file = io.TextIOWrapper(raw_file, encoding="utf-8-sig")

            for row in csv.DictReader(text_file):
                if row["sensorid"] != sensor_id:
                    continue

                # CSV rows can repeat measurements, so count rows and
                # unique measurement pairs separately.
                rows_for_sensor += 1

                for measurement in json.loads(row["jsondata"]):
                    variable = measurement.get("variable", {})
                    if variable.get("name") != "Carbon dioxide":
                        continue

                    for item in measurement.get("values", []):
                        timestamp = item.get("time")
                        value = item.get("value")

                        if timestamp is not None and value is not None:
                            # Collapse identical repeats while retaining
                            # different values recorded at the same time.
                            readings[(timestamp, value)] = None

    timestamps = [timestamp for timestamp, _ in readings]
    timestamp_counts = Counter(timestamps)

    # Each retained pair has a different value at its timestamp.
    # A count above one therefore identifies a conflicting timestamp.
    conflicting_timestamps = sum(
        count > 1 for count in timestamp_counts.values()
    )

    print(f"Sensor ID: {sensor_id}")
    print(f"CSV rows for sensor: {rows_for_sensor}")
    print(f"Distinct timestamp/value pairs: {len(readings)}")
    print(f"Distinct measurement timestamps: {len(timestamp_counts)}")
    print(
        f"Timestamps with conflicting CO2 values: "
        f"{conflicting_timestamps}"
    )
    print("Unit: ppm")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: python src/audit.py path/to/environment.zip"
        )
    audit(sys.argv[1])
