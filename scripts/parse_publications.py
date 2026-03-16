#!/usr/bin/env python3
"""Parse publications from the Catalan markdown file into structured JSON."""

import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote

# Section heading patterns mapped to types
SECTION_MAP = [
    ("Articles en revistes indexades (JCR, SJR, SCOPUS)", "indexed-jcr"),
    ("Articles en revistes indexades en altres índex", "indexed-other"),
    ("Articles en revistes no indexades amb avaluació externa", "non-indexed"),
    ("Publicacions derivades de congressos", "conference-derived"),
    ("Altres publicacions", "other"),
]


def detect_section(line):
    """Check if a line is a section heading and return the type."""
    clean = line.replace("**", "").replace("*", "").strip().rstrip(":")
    for heading, pub_type in SECTION_MAP:
        if heading.lower() in clean.lower():
            return pub_type
    return None


def join_entry_lines(raw_text):
    """Split raw section text into individual entry strings (separated by blank lines)."""
    entries = []
    current = []
    for line in raw_text.split("\n"):
        if line.strip() == "":
            if current:
                entries.append(" ".join(current))
                current = []
        else:
            current.append(line.strip())
    if current:
        entries.append(" ".join(current))
    return entries


def extract_authors_and_rest(text):
    """Split text into authors (before year) and the rest (after year)."""
    m = re.search(r'^(.*?)\((\d{4})\)\.?\s*', text)
    if m:
        authors = m.group(1).strip().rstrip(',').rstrip('.').strip()
        year = int(m.group(2))
        rest = text[m.end():]
        return authors, year, rest
    return None, None, text


def extract_title_and_url(rest):
    """Extract title and URL from the rest of the entry after the year."""
    title = ""
    url = ""

    # Find ALL markdown links [text](url) to handle multi-link titles
    link_pattern = re.compile(r'\[([^\]]*)\]\(([^)]+)\)')
    links = list(link_pattern.finditer(rest))

    if links:
        # Collect all link texts as the title (some entries split title across links)
        # Use the first link's URL as the canonical URL
        url = links[0].group(2).strip()

        # Build title from all consecutive links at the start
        title_parts = []
        last_end = links[0].start()
        for link in links:
            # Only include links that are part of the title (before journal info)
            # Stop if there's substantial non-link text between links
            gap = rest[last_end:link.start()].strip()
            if last_end > links[0].start() and len(gap) > 2 and not gap.startswith('['):
                break
            title_parts.append(link.group(1).strip())
            last_end = link.end()

        title = ' '.join(title_parts)
        after_link = rest[last_end:]
    else:
        after_link = rest
        title = ""

    # Clean up title: remove markdown artifacts
    title = title.replace("[", "").replace("]", "")
    # Remove trailing/leading punctuation artifacts
    title = title.strip().strip('.').strip(',').strip(':').strip()
    # Remove wrapping italics from title
    if title.startswith('*') and title.endswith('*'):
        title = title[1:-1].strip()

    return title, url, after_link if links else rest


def extract_doi(url):
    """Extract DOI from URL if present."""
    if not url:
        return ""
    # URL-decode to handle %2F etc. in DOI strings
    decoded = unquote(url)
    m = re.search(r'doi\.org/(10\.\d{4,}/[^\s&]+)', decoded)
    if m:
        return m.group(1).rstrip('/')
    # DOI embedded in path (e.g. wiley.com/doi/10.xxxx/yyyy/abstract)
    m = re.search(r'/doi/(10\.\d{4,}/[^/\s&]+)', decoded)
    if m:
        return m.group(1)
    # DOI in query params (e.g. tandfonline doSearch)
    if 'doSearch' in decoded or 'AllField' in decoded:
        m = re.search(r'10\.\d{4,}/[^\s&)]+', decoded)
        if m:
            return m.group(0)
    return ""


def parse_journal_block(text):
    """Parse journal, volume, issue, pages from the text after the title/URL.

    Returns (journal, volume, issue, pages).
    """
    journal = ""
    volume = ""
    issue = ""
    pages = ""

    # Clean the text
    text = text.strip()
    # Remove markdown link artifacts like [.](url) or *[.](url)
    text = re.sub(r'\*?\[\.?\]\([^)]*\)\s*', '', text)
    # Remove {.underline} and similar attributes
    text = re.sub(r'\{[^}]*\}', '', text)
    text = text.lstrip('.').lstrip(',').strip()

    # Remove stray single * markers that aren't part of proper italic pairs
    # Count asterisks: if odd number, remove unpaired ones adjacent to non-word chars
    if text.count('*') % 2 == 1:
        # Remove a lone * that sits between a digit/word and a parenthesis, e.g. "12*(3)"
        text = re.sub(r'(\d)\*(\()', r'\1\2', text)

    # Normalize stray bold/italic markers
    text = text.replace('** *', ' *').replace('** **', ' ')
    # Remove standalone ** (bold markers that aren't useful)
    text = re.sub(r'\*\*\s*\*\*', '', text)
    text = re.sub(r'\*\*', '', text)

    # Handle pattern where italic starts mid-word: Rev*ista Ciències* → *Revista Ciències*
    # Look for word fragment immediately before *italic*
    text = re.sub(r'(\w+)\*(\w[^*]*)\*', lambda m: '*' + m.group(1) + m.group(2) + '*', text)

    # Handle multiple adjacent italic blocks: *Journal* *29* → *Journal, 29*
    # Merge adjacent *...* *...* into one
    text = re.sub(r'\*([^*]+)\*\s*\*([^*]+)\*', r'*\1, \2*', text)

    # Try to find italic journal text: *....*
    # Handle cases where the italic wraps journal+vol: *Journal, Vol*(Issue)
    # or *Journal, Vol(Issue),* Pages
    italic_match = re.search(r'\*([^*]+)\*', text)

    if not italic_match:
        # No italic — try to parse plain text (e.g. "Enseñanza de las Ciencias 27 (1), 5-18")
        # Look for a recognizable pattern: text followed by number(number), pages
        m = re.search(r'^(.+?)\s+(\d+)\s*(?:\(([^)]+)\))?\s*,?\s*(?:pp?\.?\s*)?(\d+[-–]\d+)?', text)
        if m:
            journal = m.group(1).strip().rstrip(',')
            volume = m.group(2)
            issue = m.group(3) or ""
            pages = (m.group(4) or "").replace('–', '-')
        return journal, volume, issue, pages

    journal_raw = italic_match.group(1).strip()
    after_italic = text[italic_match.end():].strip()

    # Remove backslashes (line continuation in markdown)
    journal_raw = journal_raw.replace('\\', '').strip()

    # Combine journal_raw and after_italic for full parsing context
    # The split between italic and non-italic is arbitrary in the source markdown,
    # so we treat the full string as: journal_name, volume(issue), pages
    full_info = journal_raw
    if after_italic:
        full_info = full_info.rstrip(',').rstrip() + ', ' + after_italic.lstrip(',').lstrip('.').strip()

    # Remove trailing noise: pp, page markers, etc. at the very end
    # Clean up: remove {.underline} and similar
    full_info = re.sub(r'\{[^}]*\}', '', full_info)

    # Strategy: find volume/issue/pages pattern in the full string
    # Pattern: "Journal Name, Vol(Issue), Pages" or "Journal Name, Vol, Pages"
    # The journal name is everything before the first number that looks like a volume

    # Try: journal, vol(issue), pp-pp
    m = re.search(
        r'^(.+?),\s*(\d+)\s*(?:\(([^)]+)\))?\s*'
        r'(?:,\s*(?:pp?\.?\s*)?(\d+[-–]\d+|\d+))?\s*$',
        full_info.rstrip('.').rstrip(',').strip()
    )
    if not m:
        # Try without strict end anchor — just find vol/issue/pages somewhere
        m = re.search(
            r'^(.+?),\s*(\d+)\s*(?:\(([^)]+)\))?\s*'
            r'(?:,\s*(?:pp?\.?\s*)?(\d+[-–]\d+|\d+))?',
            full_info.rstrip('.').rstrip(',').strip()
        )

    if m:
        journal = m.group(1).strip().rstrip(',')
        volume = m.group(2)
        issue = m.group(3) or ""
        pages_raw = m.group(4) or ""
        if pages_raw:
            pages = pages_raw.replace('–', '-')

        # If we got pages but no dash, check if it's really just a single page number
        # or if we can find actual page range in the remaining text
        if not pages:
            remaining = full_info[m.end():].strip()
            pages_m = re.search(r'(?:pp?\.?\s*)?(\d+[-–]\d+)', remaining)
            if pages_m:
                pages = pages_m.group(1).replace('–', '-')
    else:
        # Fallback: just use the journal_raw as journal name
        journal = journal_raw.strip().rstrip(',')
        remaining = after_italic.lstrip(',').lstrip('.').strip()

        # Try to find volume in remaining
        vol_m = re.search(r'^(\d+)\s*(?:\(([^)]+)\))?', remaining)
        if vol_m:
            volume = vol_m.group(1)
            if vol_m.group(2):
                issue = vol_m.group(2)
            remaining = remaining[vol_m.end():].lstrip(',').strip()

        # Try to find pages in remaining
        pages_m = re.search(r'(?:pp?\.?\s*)?(\d+[-–]\d+)', remaining)
        if pages_m:
            pages = pages_m.group(1).replace('–', '-')

    # Check if "pendent numeració" appears (meaning pages pending)
    if 'pendent' in full_info.lower():
        pages = ""

    # Clean journal name
    journal = journal.strip().rstrip(',').rstrip('.').strip()
    journal = re.sub(r'\[|\]', '', journal)

    return journal, volume, issue, pages


def parse_entry(text, pub_type):
    """Parse a single publication entry into a dict."""
    entry = {
        "year": None,
        "authors": "",
        "title": "",
        "journal": "",
        "volume": "",
        "issue": "",
        "pages": "",
        "doi": "",
        "url": "",
        "type": pub_type,
    }

    authors, year, rest = extract_authors_and_rest(text)
    entry["year"] = year
    if authors:
        entry["authors"] = authors

    title, url, after_title = extract_title_and_url(rest)
    entry["title"] = title
    entry["url"] = url
    entry["doi"] = extract_doi(url)

    journal, volume, issue, pages = parse_journal_block(after_title)
    entry["journal"] = journal
    entry["volume"] = volume
    entry["issue"] = issue
    entry["pages"] = pages

    # If title is empty, try to extract from plain text (no URL entries)
    if not entry["title"] and rest:
        # For entries without URLs, title is before the journal (first italic) or the whole rest
        italic_pos = rest.find('*')
        if italic_pos > 0:
            entry["title"] = rest[:italic_pos].strip().rstrip('.').rstrip(',').strip()
        else:
            # Conference entries with no URL and no journal — title is the whole rest
            entry["title"] = rest.strip().rstrip('.').strip()

    # Clean up title: remove stray ** markers and leading/trailing punctuation
    entry["title"] = entry["title"].replace('**', '').strip().strip('.').strip()
    # Remove escaped quotes
    entry["title"] = entry["title"].replace('\\"', '"')
    # Remove escaped apostrophes
    entry["title"] = entry["title"].replace("\\'", "'")

    # Clean authors: remove escaped chars
    entry["authors"] = entry["authors"].replace("\\...", "...").replace("\\…", "…")

    return entry


def parse_publications(md_path):
    """Parse the full markdown file into a list of publication dicts."""
    text = Path(md_path).read_text(encoding="utf-8")

    # Remove front matter
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            text = text[end + 3:]

    publications = []
    current_type = None
    current_section_text = []

    for line in text.split("\n"):
        section = detect_section(line)
        if section:
            # Process previous section
            if current_type and current_section_text:
                raw = "\n".join(current_section_text)
                entries = join_entry_lines(raw)
                for entry_text in entries:
                    if entry_text.strip():
                        pub = parse_entry(entry_text, current_type)
                        if pub["year"]:
                            publications.append(pub)
            current_type = section
            current_section_text = []
        elif current_type:
            current_section_text.append(line)

    # Process last section
    if current_type and current_section_text:
        raw = "\n".join(current_section_text)
        entries = join_entry_lines(raw)
        for entry_text in entries:
            if entry_text.strip():
                pub = parse_entry(entry_text, current_type)
                if pub["year"]:
                    publications.append(pub)

    # Sort by year descending
    publications.sort(key=lambda x: x["year"] or 0, reverse=True)

    return publications


def main():
    base = Path(__file__).resolve().parent.parent
    md_path = base / "content" / "ca" / "publicacions-cientifiques.md"
    out_path = base / "data" / "publications.json"

    if not md_path.exists():
        print(f"ERROR: {md_path} not found", file=sys.stderr)
        sys.exit(1)

    publications = parse_publications(md_path)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(publications, f, ensure_ascii=False, indent=2)

    # Report
    from collections import Counter
    counts = Counter(p["type"] for p in publications)
    print(f"Total publications parsed: {len(publications)}")
    for pub_type, count in sorted(counts.items()):
        print(f"  {pub_type}: {count}")
    print(f"\nOutput written to {out_path}")


if __name__ == "__main__":
    main()
