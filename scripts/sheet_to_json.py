#!/usr/bin/env python3
"""Fetch data from Google Sheets tabs and write JSON data files."""

import json
import os
import sys

from google.oauth2 import service_account
from googleapiclient.discovery import build

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
        "enums": {},
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
        "enums": {},
    },
}

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


def get_sheets_service():
    """Build and return a Google Sheets API service."""
    key_json = os.environ.get("GOOGLE_SHEETS_KEY")
    if not key_json:
        print("ERROR: GOOGLE_SHEETS_KEY environment variable is not set.")
        sys.exit(1)

    sheet_id = os.environ.get("GOOGLE_SHEET_ID")
    if not sheet_id:
        print("ERROR: GOOGLE_SHEET_ID environment variable is not set.")
        sys.exit(1)

    creds_info = json.loads(key_json)
    creds = service_account.Credentials.from_service_account_info(
        creds_info, scopes=SCOPES
    )
    service = build("sheets", "v4", credentials=creds)
    return service.spreadsheets(), sheet_id


def fetch_tab(sheets, sheet_id, tab_name):
    """Fetch all rows from a tab and return list of dicts."""
    result = sheets.values().get(
        spreadsheetId=sheet_id, range=f"{tab_name}!A:ZZ"
    ).execute()
    rows = result.get("values", [])
    if len(rows) < 2:
        return []

    headers = [h.strip().lower() for h in rows[0]]
    entries = []
    for row in rows[1:]:
        # Skip empty rows
        if not any(cell.strip() for cell in row if cell):
            continue
        entry = {}
        for i, header in enumerate(headers):
            if not header:
                continue
            value = row[i].strip() if i < len(row) else ""
            # Strip whitespace-only cells to empty string
            if not value:
                value = ""
            entry[header] = value
        # Skip rows where all values are empty
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
            if val == "" or (isinstance(val, str) and not val.strip()):
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
    sheets, sheet_id = get_sheets_service()
    all_errors = []

    for tab_name, config in TAB_CONFIG.items():
        print(f"Processing tab: {tab_name}")
        entries = fetch_tab(sheets, sheet_id, tab_name)
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
