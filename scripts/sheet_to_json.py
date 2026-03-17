#!/usr/bin/env python3
"""Fetch data from a public Google Sheet (CSV export) and write JSON data files."""

import csv
import io
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

# Tab-to-file mapping with required fields and enum validation.
TAB_CONFIG = {
    "Publications": {
        "file": "data/publications.json",
        "required": ["year", "authors", "title"],
        "enums": {
            "type": [
                "indexed-jcr",
                "indexed-other",
                "non-indexed",
                "conference-derived",
                "other",
            ],
        },
    },
    "Projects": {
        "file": "data/projects.json",
        "required": ["code", "title"],
        "enums": {
            "section": ["competitive", "networks"],
            "pi_role": ["ip", "ip-national", "other-pi"],
        },
    },
    "Books": {
        "file": "data/books.json",
        "required": ["year", "authors", "title"],
        "enums": {
            "type": ["chapter", "edited-book", "proceedings"],
        },
    },
    "Conferences": {
        "file": "data/conferences.json",
        "required": ["year", "authors", "title"],
        "enums": {
            "type": ["oral", "plenary", "poster", "symposium"],
        },
    },
    "Talks": {
        "file": "data/talks.json",
        "required": ["year", "title"],
    },
    "Contracts": {
        "file": "data/contracts.json",
        "required": ["title"],
        "enums": {
            "pi_role": ["ip", "other-pi"],
        },
    },
    "Theses": {
        "file": "data/theses.json",
        "required": ["year", "author", "title"],
        "enums": {
            "type": ["phd", "master"],
            "status": ["completed", "in-progress"],
        },
    },
    "Materials": {
        "file": "data/materials.json",
        "required": ["year", "title"],
    },
}


def fetch_tab(sheet_id, tab_name):
    """Fetch all rows from a public sheet tab via CSV export."""
    url = (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}"
        f"/gviz/tq?tqx=out:csv&sheet={urllib.parse.quote(tab_name)}"
    )
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            text = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        print(f"ERROR: Failed to fetch tab '{tab_name}': HTTP {e.code}")
        print("  Is the Google Sheet set to 'Anyone with the link can view'?")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"ERROR: Failed to fetch tab '{tab_name}': {e.reason}")
        sys.exit(1)

    reader = csv.DictReader(io.StringIO(text))
    # Normalize headers to lowercase stripped
    if reader.fieldnames is None:
        return []
    clean_fieldnames = [h.strip().lower() for h in reader.fieldnames]
    reader.fieldnames = clean_fieldnames

    entries = []
    for row in reader:
        entry = {}
        for key, value in row.items():
            if not key:
                continue
            entry[key] = value.strip() if value else ""
        if not any(entry.values()):
            continue
        entries.append(entry)
    return entries


def convert_year(entries):
    """Convert 'year' column to int where present."""
    for entry in entries:
        if "year" in entry and entry["year"]:
            try:
                entry["year"] = int(entry["year"])
            except (ValueError, TypeError):
                pass  # Leave as-is; validation will catch issues
    return entries


def sort_by_year(entries):
    """Sort entries by year descending."""
    def year_key(e):
        y = e.get("year", 0)
        return y if isinstance(y, int) else 0
    return sorted(entries, key=year_key, reverse=True)


def validate(entries, tab_name, config):
    """Validate required fields and enum values. Return list of errors."""
    errors = []
    required = config.get("required", [])
    enums = config.get("enums", {})

    for i, entry in enumerate(entries):
        row_num = i + 2  # 1-indexed, skip header row
        for field in required:
            val = entry.get(field, "")
            if val == "":
                errors.append(
                    f"{tab_name} row {row_num}: missing required field '{field}'"
                )
        for field, allowed in enums.items():
            val = entry.get(field, "")
            if val and val not in allowed:
                errors.append(
                    f"{tab_name} row {row_num}: invalid '{field}' value "
                    f"'{val}' (allowed: {allowed})"
                )
    return errors


def write_json(filepath, entries):
    """Write entries to a JSON file."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"  Wrote {len(entries)} entries to {filepath}")


def main():
    sheet_id = os.environ.get("GOOGLE_SHEET_ID")
    if not sheet_id:
        print("ERROR: GOOGLE_SHEET_ID environment variable is not set.")
        sys.exit(1)

    all_errors = []

    for tab_name, config in TAB_CONFIG.items():
        print(f"Processing tab: {tab_name}")
        entries = fetch_tab(sheet_id, tab_name)
        entries = convert_year(entries)
        entries = sort_by_year(entries)

        errors = validate(entries, tab_name, config)
        all_errors.extend(errors)

        # Write files even if validation fails (for debugging)
        write_json(config["file"], entries)

    if all_errors:
        print(f"\nValidation failed with {len(all_errors)} error(s):")
        for err in all_errors:
            print(f"  - {err}")
        sys.exit(1)

    print("\nAll tabs processed successfully.")


if __name__ == "__main__":
    main()
