#!/usr/bin/env python3
"""
Generate a Zotero-compatible RIS file from Digna Couso's publication markdown files.

Parses:
  - content/ca/publicacions-cientifiques.md (articles, conference papers, other pubs)
  - content/ca/llibres-i-capitols.md (books, book chapters, proceedings, edited books)

Outputs:
  - static/publications/couso-publications.ris
"""

import re
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)

ARTICLES_FILE = os.path.join(ROOT_DIR, "content/ca/publicacions-cientifiques.md")
BOOKS_FILE = os.path.join(ROOT_DIR, "content/ca/llibres-i-capitols.md")
OUTPUT_FILE = os.path.join(ROOT_DIR, "static/publications/couso-publications.ris")

# Section headers mapped to RIS types
SECTION_TYPES = {
    # publicacions-cientifiques.md
    "articles en revistes indexades (jcr, sjr, scopus)": "JOUR",
    "articles en revistes indexades en altres índex (in-recs, latindex, etc)": "JOUR",
    "articles en revistes no indexades amb avaluació externa": "JOUR",
    "publicacions derivades de congressos": "CPAPER",
    "altres publicacions": "GEN",
    # llibres-i-capitols.md
    "llibres": "BOOK",
    "capítols de llibre": "CHAP",
    "proceedings": "CPAPER",
    "edicions": "EDBOOK",
}


def normalize_section(header):
    """Normalize a section header for matching."""
    h = header.lower().strip().rstrip(":")
    h = re.sub(r"\*+", "", h).strip()
    return h


def read_markdown(filepath):
    """Read markdown file, strip front matter, return content."""
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()
    # Strip YAML front matter
    text = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.DOTALL)
    return text


def split_sections(text):
    """Split markdown text into (section_header, entries_text) pairs."""
    # Sections are marked with **Header:** or **Header**
    pattern = r"\*\*([^*]+?)\*\*\s*\n"
    parts = re.split(pattern, text)
    sections = []
    # parts[0] is text before first header (usually empty)
    for i in range(1, len(parts), 2):
        header = parts[i].strip().rstrip(":")
        body = parts[i + 1] if i + 1 < len(parts) else ""
        sections.append((header, body))
    return sections


def join_multiline_entries(text):
    """Join continuation lines into single-line entries.

    Entries are separated by blank lines. Continuation lines start with
    lowercase or special chars and should be joined to the previous line.
    """
    lines = text.split("\n")
    entries = []
    current = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current:
                entries.append(" ".join(current))
                current = []
        else:
            current.append(stripped)

    if current:
        entries.append(" ".join(current))

    return entries


def clean_markdown(text):
    """Remove markdown formatting: links, bold, italic, underline spans."""
    # Remove markdown links [text](url) -> text
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    # Remove bold/italic markers
    text = re.sub(r"\*+", "", text)
    # Remove {.underline} spans
    text = re.sub(r"\{\.underline\}", "", text)
    # Remove HTML-ish remnants
    text = re.sub(r"<[^>]+>", "", text)
    # Fix escaped quotes from markdown (e.g., \' -> ')
    text = text.replace("\\'", "'")
    text = text.replace('\\"', '"')
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_doi(text):
    """Extract DOI from text."""
    # Match https://doi.org/... or doi:...
    m = re.search(r"https?://doi\.org/(10\.\S+)", text)
    if m:
        doi = m.group(1).rstrip(".,;)")
        return doi
    m = re.search(r"\bdoi:\s*(10\.\S+)", text, re.IGNORECASE)
    if m:
        return m.group(1).rstrip(".,;)")
    return None


def extract_url(text):
    """Extract URL from markdown link or plain URL (not DOI)."""
    # First try markdown links
    m = re.search(r"\]\((https?://[^)]+)\)", text)
    if m:
        url = m.group(1)
        if "doi.org" not in url:
            return url
    # Try plain URLs
    m = re.search(r"(https?://\S+)", text)
    if m:
        url = m.group(1).rstrip(".,;)")
        if "doi.org" not in url:
            return url
    # Try relative URLs like /pdf/...
    m = re.search(r"\]\((/[^)]+)\)", text)
    if m:
        return m.group(1)
    return None


def extract_year(text):
    """Extract publication year from parenthesized year after authors."""
    m = re.search(r"\((\d{4})(?:/\d{4})?\)", text)
    if m:
        return m.group(1)
    # Try just a 4-digit year
    m = re.search(r"\b(19\d{2}|20\d{2})\b", text)
    if m:
        return m.group(1)
    return None


def extract_pages(text):
    """Extract page range from text. Returns (start, end) or (None, None)."""
    # pp. X-Y or pp.X-Y
    m = re.search(r"pp\.?\s*(\d+)\s*[-–]\s*(\d+)", text)
    if m:
        return m.group(1), m.group(2)
    # Pages like 1301-1321
    m = re.search(r"\b(\d{2,5})\s*[-–]\s*(\d{2,5})\b", text)
    if m:
        # Avoid matching years like 2020-2021
        start, end = int(m.group(1)), int(m.group(2))
        if start < 10000 and end < 10000 and start < end and not (1900 <= start <= 2100):
            return m.group(1), m.group(2)
    return None, None


def extract_volume_issue(text):
    """Extract volume and issue number. Returns (volume, issue)."""
    # Pattern: Volume(Issue) e.g., 24(2) or 18(1)
    m = re.search(r"\b(\d{1,3})\s*\((\d{1,3})\)", text)
    if m:
        vol, issue = m.group(1), m.group(2)
        # Avoid matching years
        if int(vol) < 200:
            return vol, issue
    # Volume only, e.g., "54" after journal name
    m = re.search(r",\s*(\d{1,3})\b", text)
    if m and int(m.group(1)) < 200:
        return m.group(1), None
    return None, None


def parse_authors_and_rest(entry_text):
    """Split entry into authors string and the rest (after year)."""
    # Pattern: Authors (Year). Rest...
    # Authors end at the (YYYY) pattern
    m = re.match(r"^(.+?)\s*\((\d{4}(?:/\d{4})?)\)\s*\.?\s*(.*)$", entry_text, re.DOTALL)
    if m:
        return m.group(1).strip(), m.group(2), m.group(3).strip()
    return None, None, entry_text


def parse_author_names(authors_str):
    """Parse author string into list of 'Last, First' names."""
    # Clean up
    authors_str = authors_str.strip().rstrip(".")
    # Remove (Secretaria Ejecutiva) and similar parenthetical roles
    authors_str = re.sub(r"\([^)]*\)", "", authors_str)
    # Remove "et al."
    authors_str = re.sub(r"\bet al\.?", "", authors_str)
    # Replace & and "and" with comma
    authors_str = re.sub(r"\s*[&]\s*", ", ", authors_str)
    # Replace semicolons with commas
    authors_str = authors_str.replace(";", ",")
    # Remove ... or …
    authors_str = re.sub(r"\.{3}|…", ",", authors_str)

    # Split on commas, but be smart about "Last, First" pairs
    # Academic format: "Last1, F1., Last2, F2., Last3, F3."
    # Or: "Last1, F1., Last2, F2. & Last3, F3."
    parts = [p.strip().rstrip(".") for p in authors_str.split(",") if p.strip()]

    authors = []
    i = 0
    while i < len(parts):
        part = parts[i].strip()
        if not part:
            i += 1
            continue

        # Check if next part looks like initials (short, has uppercase and dots)
        if i + 1 < len(parts):
            next_part = parts[i + 1].strip()
            # Initials: short (≤6 chars when stripped), or contains dots/single caps
            is_initials = (
                len(next_part.replace(".", "").replace(" ", "")) <= 4
                or re.match(r"^[A-ZÀ-Ú][a-zà-ú]?\.?\s*[A-ZÀ-Ú]?\.?$", next_part)
                or re.match(r"^[A-ZÀ-Ú]\.$", next_part)
            )
            # Also check: if the part after next_part looks like a last name (starts with capital),
            # then next_part is likely initials
            if is_initials:
                authors.append(f"{part}, {next_part}")
                i += 2
                continue

        # Single name or already "Last, First" in one chunk
        if part:
            authors.append(part)
        i += 1

    return [a for a in authors if a and len(a) > 1]


def extract_journal_name(text):
    """Extract journal/book name from italicized text."""
    # Look for text between * markers (italic in markdown)
    m = re.search(r"\*([^*]+)\*", text)
    if m:
        journal = m.group(1).strip().rstrip(",").strip()
        # Remove volume/issue that might be inside italics
        journal = re.sub(r",?\s*\d{1,3}\s*\(\d{1,3}\)\s*$", "", journal)
        journal = re.sub(r",?\s*\d{1,3}\s*$", "", journal)
        return journal.strip().rstrip(",").strip()
    return None


def extract_book_info(rest_text):
    """For book chapters, extract book title, editors, publisher, pages."""
    info = {}

    # Look for "Dins de" or "In:" or "En:" pattern for chapters
    chapter_pattern = re.search(
        r"(?:Dins de|In[:\s]|En[:\s])\s*(.+?)(?:\*(.+?)\*)", rest_text
    )
    if chapter_pattern:
        editors_str = chapter_pattern.group(1).strip()
        book_title = chapter_pattern.group(2).strip().rstrip(",").strip()
        info["book_title"] = book_title
        info["editors"] = editors_str

    # Publisher: often the last word/phrase before the period
    # Common publishers: Springer, Graó, Routledge, etc.
    publisher_pattern = re.search(
        r"(?:Springer|Graó|Routledge|Penguin|Waxmann|IOS Press|FECYT|"
        r"Colciencias|Didácticas Magisterio|StudienVerlag|StdudienVerlag|"
        r"Fundació Bofill|University of [\w]+|Servei de Publicacions|"
        r"Editorial [\w]+|Publicacions [\w]+|European Science Education|"
        r"Lorentz Center|AMSTEL institute|Pegen Akademy|University of Cyprus)",
        rest_text,
        re.IGNORECASE,
    )
    if publisher_pattern:
        info["publisher"] = publisher_pattern.group(0)

    # Pages in parentheses: (pp. X-Y) or (pp X-Y)
    pages_m = re.search(r"\(pp\.?\s*(\d+)\s*[-–]\s*(\d+)\)", rest_text)
    if pages_m:
        info["sp"] = pages_m.group(1)
        info["ep"] = pages_m.group(2)

    return info


def extract_title(rest_text):
    """Extract the title from the rest of the entry (after year).

    Title is the text before the journal name (first italic text),
    or before 'Dins de'/'In:'/'En:' for chapters.
    """
    # Remove leading markdown link brackets but keep the text
    text = rest_text

    # For chapters: title is before "Dins de" / "In:" / "En:"
    chapter_split = re.split(r"\s+(?:Dins de|In[:\s]|En[:\s])", text, maxsplit=1)
    if len(chapter_split) > 1:
        title_part = chapter_split[0]
    else:
        # For articles: title is before the journal name in italics
        # Split at first *Journal*
        title_part = re.split(r"\*[^*]+\*", text, maxsplit=1)[0]

    # Clean the title
    title = clean_markdown(title_part)
    # Remove trailing period, comma
    title = title.strip().rstrip(".,").strip()
    # Remove leading [ or trailing ]
    title = title.strip("[]")
    return title


def parse_entry(entry_text, ris_type):
    """Parse a single publication entry and return a dict of RIS fields."""
    if not entry_text or len(entry_text) < 20:
        return None

    # Skip entries that are just section artifacts
    if entry_text.startswith("**") or entry_text.startswith("---"):
        return None

    record = {"TY": ris_type}

    # Extract DOI and URL before cleaning
    doi = extract_doi(entry_text)
    if doi:
        record["DO"] = doi

    url = extract_url(entry_text)
    if url:
        record["UR"] = url

    # Parse authors, year, and rest
    authors_str, year, rest = parse_authors_and_rest(entry_text)
    if not authors_str:
        return None

    # Year
    if year:
        record["PY"] = year.split("/")[0]  # Take first year if range
    else:
        yr = extract_year(entry_text)
        if yr:
            record["PY"] = yr

    # Authors
    author_list = parse_author_names(authors_str)
    if author_list:
        record["AU"] = author_list

    # Title
    title = extract_title(rest)
    if title:
        record["TI"] = title

    # For book chapters, extract book info
    if ris_type in ("CHAP", "CPAPER"):
        book_info = extract_book_info(rest)
        if "book_title" in book_info:
            record["T2"] = book_info["book_title"]
        if "publisher" in book_info:
            record["PB"] = book_info["publisher"]
        if "sp" in book_info:
            record["SP"] = book_info["sp"]
            record["EP"] = book_info["ep"]
    elif ris_type in ("BOOK", "EDBOOK"):
        # Extract publisher for books/edited books
        book_info = extract_book_info(rest)
        if "publisher" in book_info:
            record["PB"] = book_info["publisher"]
            # Clean publisher from title if it was included
            if "TI" in record:
                pub = book_info["publisher"]
                record["TI"] = re.sub(
                    r"\.?\s*" + re.escape(pub) + r".*$", "", record.get("TI", "")
                ).strip().rstrip(".,")

    # Journal name (for articles)
    if ris_type in ("JOUR", "GEN"):
        journal = extract_journal_name(rest)
        if journal:
            record["JO"] = journal

    # For edited books, extract series title from italics
    if ris_type == "EDBOOK":
        journal = extract_journal_name(rest)
        if journal:
            record["T2"] = journal

    # Volume and issue (for articles)
    if ris_type == "JOUR":
        vol, issue = extract_volume_issue(rest)
        if vol:
            record["VL"] = vol
        if issue:
            record["IS"] = issue

    # Pages (for articles if not already set for chapters)
    if "SP" not in record:
        sp, ep = extract_pages(rest)
        if sp:
            record["SP"] = sp
        if ep:
            record["EP"] = ep

    return record


def clean_field(value):
    """Clean a field value: fix escaped quotes, trim whitespace."""
    value = value.replace("\\'", "'").replace('\\"', '"')
    value = value.replace("\\", "")
    return value.strip()


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

    lines.append("ER  - ")
    return "\n".join(lines)


def process_file(filepath, default_type=None):
    """Process a markdown file and return list of RIS records."""
    text = read_markdown(filepath)
    sections = split_sections(text)
    records = []

    for header, body in sections:
        norm_header = normalize_section(header)
        ris_type = None
        for key, rtype in SECTION_TYPES.items():
            if key in norm_header or norm_header in key:
                ris_type = rtype
                break

        if not ris_type:
            ris_type = default_type or "GEN"

        entries = join_multiline_entries(body)
        for entry in entries:
            record = parse_entry(entry, ris_type)
            if record and record.get("TI"):
                records.append(record)

    return records


def main():
    records = []

    # Process articles file
    print(f"Processing {ARTICLES_FILE}...")
    articles = process_file(ARTICLES_FILE, default_type="JOUR")
    print(f"  Found {len(articles)} entries")
    records.extend(articles)

    # Process books file
    print(f"Processing {BOOKS_FILE}...")
    books = process_file(BOOKS_FILE, default_type="CHAP")
    print(f"  Found {len(books)} entries")
    records.extend(books)

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
