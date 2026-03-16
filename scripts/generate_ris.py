#!/usr/bin/env python3
"""
Generate a Zotero-compatible RIS file from JSON data files.

Reads:
  - data/publications.json (articles, conference papers, other pubs)
  - data/books.json (books, book chapters, proceedings, edited books)

Outputs:
  - static/publications/couso-publications.ris
"""

import json
import os
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)

PUBLICATIONS_FILE = os.path.join(ROOT_DIR, "data/publications.json")
BOOKS_FILE = os.path.join(ROOT_DIR, "data/books.json")
OUTPUT_FILE = os.path.join(ROOT_DIR, "static/publications/couso-publications.ris")

# Publication type to RIS type mapping
PUBLICATION_TYPE_MAP = {
    "indexed-jcr": "JOUR",
    "indexed-other": "JOUR",
    "non-indexed": "JOUR",
    "conference-derived": "CPAPER",
    "other": "GEN",
}

# Book type to RIS type mapping
BOOK_TYPE_MAP = {
    "chapter": "CHAP",
    "book": "BOOK",
    "edited-book": "EDBOOK",
    "proceedings": "CPAPER",
}


def clean_field(value):
    """Clean a field value: fix escaped quotes, trim whitespace."""
    if not value:
        return ""
    value = value.replace("\\'", "'").replace('\\"', '"')
    value = value.replace("\\", "")
    return value.strip()


def parse_author_names(authors_str):
    """Parse author string into list of 'Last, First' names.

    Handles formats like:
      - "Couso, D., Márquez, C., & Pérez, M."
      - "Couso, D"
      - "Pérez Torres, M.; Couso, D.; Márquez, C."
    """
    if not authors_str:
        return []

    authors_str = authors_str.strip().rstrip(".")

    # Remove parenthetical roles like (Secretaria Ejecutiva)
    authors_str = re.sub(r"\([^)]*\)", "", authors_str)
    # Remove "et al."
    authors_str = re.sub(r"\bet al\.?", "", authors_str)
    # Replace & and "and" with separator
    authors_str = re.sub(r"\s*[&]\s*", ", ", authors_str)

    # If semicolons are used as author separators, split on those
    if ";" in authors_str:
        raw_authors = [a.strip().rstrip(".") for a in authors_str.split(";") if a.strip()]
        return [a for a in raw_authors if a and len(a) > 1]

    # Otherwise split on commas, pairing "Last, Initials" together
    parts = [p.strip().rstrip(".") for p in authors_str.split(",") if p.strip()]

    authors = []
    i = 0
    while i < len(parts):
        part = parts[i].strip()
        if not part:
            i += 1
            continue

        # Check if next part looks like initials
        if i + 1 < len(parts):
            next_part = parts[i + 1].strip()
            is_initials = (
                len(next_part.replace(".", "").replace(" ", "")) <= 4
                or re.match(r"^[A-ZÀ-Ú][a-zà-ú]?\.?\s*[A-ZÀ-Ú]?\.?$", next_part)
                or re.match(r"^[A-ZÀ-Ú]\.$", next_part)
            )
            if is_initials:
                authors.append(f"{part}, {next_part}")
                i += 2
                continue

        if part:
            authors.append(part)
        i += 1

    return [a for a in authors if a and len(a) > 1]


def parse_pages(pages_str):
    """Parse a pages string like '12-30' into (start, end) tuple."""
    if not pages_str:
        return None, None
    m = re.match(r"(\d+)\s*[-–]\s*(\d+)", pages_str.strip())
    if m:
        return m.group(1), m.group(2)
    # Single page
    m = re.match(r"(\d+)", pages_str.strip())
    if m:
        return m.group(1), None
    return None, None


def record_from_publication(pub):
    """Convert a publication JSON entry to a RIS record dict."""
    ris_type = PUBLICATION_TYPE_MAP.get(pub.get("type", ""), "GEN")
    record = {"TY": ris_type}

    # Authors
    author_list = parse_author_names(pub.get("authors", ""))
    if author_list:
        record["AU"] = author_list

    # Title
    title = pub.get("title", "").strip().rstrip(".")
    if title:
        record["TI"] = title

    # Journal
    journal = pub.get("journal", "").strip()
    if journal:
        record["JO"] = journal

    # Volume
    volume = pub.get("volume", "").strip()
    if volume:
        record["VL"] = volume

    # Issue
    issue = pub.get("issue", "").strip()
    if issue:
        record["IS"] = issue

    # Pages
    sp, ep = parse_pages(pub.get("pages", ""))
    if sp:
        record["SP"] = sp
    if ep:
        record["EP"] = ep

    # Year
    year = pub.get("year")
    if year:
        record["PY"] = str(year)

    # DOI
    doi = pub.get("doi", "").strip()
    if doi:
        record["DO"] = doi

    # URL
    url = pub.get("url", "").strip()
    if url:
        record["UR"] = url

    return record


def record_from_book(book):
    """Convert a book JSON entry to a RIS record dict."""
    ris_type = BOOK_TYPE_MAP.get(book.get("type", ""), "CHAP")
    record = {"TY": ris_type}

    # Authors
    author_list = parse_author_names(book.get("authors", ""))
    if author_list:
        record["AU"] = author_list

    # Title
    title = book.get("title", "").strip().rstrip(".")
    if title:
        record["TI"] = title

    # Book title (for chapters, proceedings)
    book_title = book.get("book_title", "").strip().rstrip(".")
    if book_title:
        record["T2"] = book_title

    # Publisher
    publisher = book.get("publisher", "").strip()
    if publisher:
        record["PB"] = publisher

    # Pages
    sp, ep = parse_pages(book.get("pages", ""))
    if sp:
        record["SP"] = sp
    if ep:
        record["EP"] = ep

    # Year
    year = book.get("year")
    if year:
        record["PY"] = str(year)

    # DOI
    doi = book.get("doi", "").strip()
    if doi:
        record["DO"] = doi

    # URL
    url = book.get("url", "").strip()
    if url:
        record["UR"] = url

    # ISBN
    isbn = book.get("isbn", "").strip()
    if isbn:
        record["SN"] = isbn

    return record


def format_ris_record(record):
    """Format a parsed record as RIS text."""
    lines = []
    lines.append(f"TY  - {record['TY']}")

    # Authors
    for author in record.get("AU", []):
        lines.append(f"AU  - {clean_field(author)}")

    # Title
    if "TI" in record:
        lines.append(f"TI  - {clean_field(record['TI'])}")

    # Journal
    if "JO" in record:
        lines.append(f"JO  - {clean_field(record['JO'])}")

    # Book title (for chapters)
    if "T2" in record:
        lines.append(f"T2  - {clean_field(record['T2'])}")

    # Volume
    if "VL" in record:
        lines.append(f"VL  - {record['VL']}")

    # Issue
    if "IS" in record:
        lines.append(f"IS  - {record['IS']}")

    # Pages
    if "SP" in record:
        lines.append(f"SP  - {record['SP']}")
    if "EP" in record:
        lines.append(f"EP  - {record['EP']}")

    # Year
    if "PY" in record:
        lines.append(f"PY  - {record['PY']}")

    # DOI
    if "DO" in record:
        lines.append(f"DO  - {record['DO']}")

    # URL
    if "UR" in record:
        lines.append(f"UR  - {record['UR']}")

    # Publisher
    if "PB" in record:
        lines.append(f"PB  - {clean_field(record['PB'])}")

    # ISBN
    if "SN" in record:
        lines.append(f"SN  - {record['SN']}")

    lines.append("ER  - ")
    return "\n".join(lines)


def main():
    records = []

    # Process publications
    print(f"Processing {PUBLICATIONS_FILE}...")
    with open(PUBLICATIONS_FILE, "r", encoding="utf-8") as f:
        publications = json.load(f)
    pub_records = []
    for pub in publications:
        record = record_from_publication(pub)
        if record.get("TI"):
            pub_records.append(record)
    print(f"  Found {len(pub_records)} entries")
    records.extend(pub_records)

    # Process books
    print(f"Processing {BOOKS_FILE}...")
    with open(BOOKS_FILE, "r", encoding="utf-8") as f:
        books = json.load(f)
    book_records = []
    for book in books:
        record = record_from_book(book)
        if record.get("TI"):
            book_records.append(record)
    print(f"  Found {len(book_records)} entries")
    records.extend(book_records)

    # Write RIS file
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for i, record in enumerate(records):
            if i > 0:
                f.write("\n")
            f.write(format_ris_record(record))
            f.write("\n")

    print(f"\nGenerated {OUTPUT_FILE}")
    print(f"Total records: {len(records)}")

    # Summary by type
    type_counts = {}
    for r in records:
        t = r["TY"]
        type_counts[t] = type_counts.get(t, 0) + 1
    for t, c in sorted(type_counts.items()):
        print(f"  {t}: {c}")


if __name__ == "__main__":
    main()
