#!/usr/bin/env python3
"""Read all JSON files from data/ and write CSV files to sheets_csv/."""

import csv
import json
import os
import sys

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "sheets_csv")


def main():
    data_dir = os.path.abspath(DATA_DIR)
    output_dir = os.path.abspath(OUTPUT_DIR)

    if not os.path.isdir(data_dir):
        print(f"ERROR: data directory not found: {data_dir}")
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)

    json_files = sorted(f for f in os.listdir(data_dir) if f.endswith(".json"))
    if not json_files:
        print("No JSON files found in data/")
        sys.exit(1)

    for json_file in json_files:
        json_path = os.path.join(data_dir, json_file)
        with open(json_path, "r", encoding="utf-8") as f:
            entries = json.load(f)

        if not isinstance(entries, list) or len(entries) == 0:
            print(f"  Skipping {json_file} (empty or not a list)")
            continue

        # Collect all field names across all entries, preserving order
        # from the first entry and adding any extra keys found later.
        fieldnames = list(entries[0].keys())
        seen = set(fieldnames)
        for entry in entries[1:]:
            for key in entry.keys():
                if key not in seen:
                    fieldnames.append(key)
                    seen.add(key)

        csv_name = json_file.replace(".json", ".csv")
        csv_path = os.path.join(output_dir, csv_name)

        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(entries)

        print(f"  Wrote {len(entries)} rows to sheets_csv/{csv_name}")

    print("\nCSV export complete.")


if __name__ == "__main__":
    main()
