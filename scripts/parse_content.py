#!/usr/bin/env python3
"""Parse remaining content types from Catalan markdown files into JSON."""

import argparse
import json
import os
import re
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT_DIR = os.path.join(BASE_DIR, "content", "ca")
DATA_DIR = os.path.join(BASE_DIR, "data")


def strip_frontmatter(text):
    """Remove YAML frontmatter from markdown."""
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            return text[end + 3:].strip()
    return text.strip()


def join_continuation_lines(text):
    """Join lines ending with backslash (Hugo continuation)."""
    return re.sub(r'\\\n', '\n', text)


def clean_text(s):
    """Clean up text: strip, remove style artifacts, collapse whitespace."""
    if not s:
        return ""
    # Remove HTML style attributes
    s = re.sub(r'\[?\]?\{style="[^"]*"\}', '', s)
    # Remove style spans like [ ]{style="..."}
    s = re.sub(r'\[\s*\]\{style="[^"]*"\}', '', s)
    # Collapse whitespace
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def extract_link(text):
    """Extract URL and cleaned text from markdown link. Returns (text, url)."""
    m = re.search(r'\[([^\]]*)\]\(([^)]+)\)', text)
    if m:
        return clean_text(m.group(1)), m.group(2).strip()
    return clean_text(text), ""


def extract_year_from_text(text):
    """Try to extract a 4-digit year from text."""
    m = re.search(r'\((\d{4})\)', text)
    if m:
        return int(m.group(1))
    m = re.search(r'\b(19\d{2}|20\d{2})\b', text)
    if m:
        return int(m.group(1))
    return 0


# =============================================================================
# 1. PROJECTS
# =============================================================================
def parse_projects():
    """Parse research projects from projectes-de-recerca.md."""
    filepath = os.path.join(CONTENT_DIR, "projectes-de-recerca.md")
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()
    text = strip_frontmatter(text)
    text = join_continuation_lines(text)

    projects = []
    current_section = "competitive"
    current_pi_role = "ip"

    # Split into blocks by empty lines
    blocks = re.split(r'\n\n+', text)

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        # Check for section headings
        if re.match(r'\*\*Projectes R\+D\+i competitius\*\*', block):
            current_section = "competitive"
            continue
        if re.match(r'\*\*Xarxes de recerca', block):
            current_section = "networks"
            continue

        # Check for PI role headings
        if re.match(r'\*\*IP:\s*Digna Couso', block):
            current_pi_role = "ip"
            continue
        if re.match(r'\*\*IP Nacional', block):
            current_pi_role = "ip-national"
            continue
        if re.match(r'\*\*Altres IP', block):
            current_pi_role = "other-pi"
            continue

        # Try to parse a project entry
        # Look for code pattern: **CODE:** or **CODE: **
        code_match = re.match(r'\*\*([^*]+?)(?::?\s*)\*\*\s*(.*)', block, re.DOTALL)
        if not code_match:
            continue

        first_field = code_match.group(1).strip().rstrip(':')
        rest = code_match.group(2).strip()

        # Skip if this looks like a heading rather than a code
        if first_field.lower().startswith('entitat') or first_field.lower().startswith('durada') or first_field.lower() == 'ip':
            continue

        # Check if first field looks like a project code (not a PI role heading)
        # Project codes typically have numbers or specific patterns
        code = first_field.strip()

        # Extract title and URL from text before the first **field** marker
        # Title is everything before the first **Entitat or similar field
        title_part_m = re.match(r'(.*?)(?=\*\*Entitat|\*\*Durada|\Z)', rest, re.DOTALL)
        title_part = title_part_m.group(1).strip() if title_part_m else rest.split('\n')[0]
        title, url = extract_link(title_part)
        if not title:
            # Title might be plain text
            title = re.sub(r'\*\*.*', '', title_part).strip().rstrip('.').strip()
            title = clean_text(title)

        # Parse remaining fields
        full_block = rest
        funding = ""
        budget = ""
        participants = ""
        duration = ""
        pi = ""

        # Funding entity
        m = re.search(r'\*\*Entitat\s+[Ff]inançadora:\*\*\s*(.*?)(?=\*\*|\Z)', full_block, re.DOTALL)
        if not m:
            m = re.search(r'\*\*Entitat\s+finançadora\*\*:\s*(.*?)(?=\*\*|\Z)', full_block, re.DOTALL)
        if m:
            raw = m.group(1).strip()
            # Try to split budget from funding entity
            # Budget often appears after a slash or period with €
            budget_m = re.search(r'[./,]\s*([\d.,]+\s*€)', raw)
            if budget_m:
                budget = budget_m.group(1).strip()
                funding = raw[:budget_m.start()].strip().rstrip('.').rstrip(',').rstrip('/')
            else:
                funding = raw
            funding = clean_text(funding)

        # Participants
        m = re.search(r'\*\*Entitats\s+[Pp]articipants?(?::\s*)?\*\*(?::?\s*)(.*?)(?=\*\*|\Z)', full_block, re.DOTALL)
        if m:
            participants = clean_text(m.group(1).strip())

        # Duration
        m = re.search(r'\*\*Durada\*\*\s*:?\s*(.*?)(?=\*\*|\Z)', full_block, re.DOTALL)
        if not m:
            m = re.search(r'\*\*Durada:\*\*\s*(.*?)(?=\*\*|\Z)', full_block, re.DOTALL)
        if m:
            duration = clean_text(m.group(1).strip().rstrip('.'))

        # PI
        m = re.search(r'\*\*IP\*\*\s*:?\s*(.*?)(?=\*\*|\Z)', full_block, re.DOTALL)
        if not m:
            m = re.search(r'\*\*IP:\*\*\s*(.*?)(?=\*\*|\Z)', full_block, re.DOTALL)
        if m:
            pi = clean_text(m.group(1).strip().rstrip('.'))

        project = {
            "code": code,
            "acronym": "",
            "title": title,
            "funding_entity": funding,
            "budget": budget,
            "duration": duration,
            "participants": participants,
            "pi": pi,
            "pi_role": current_pi_role,
            "url": url,
            "section": current_section,
        }

        # Try to extract acronym from title - usually in parentheses at end
        acro_m = re.search(r'\(([A-Z][A-Z0-9\s&-]{1,20})\)\s*$', title)
        if acro_m:
            project["acronym"] = acro_m.group(1).strip()

        # Also try link text for acronym
        if not project["acronym"]:
            link_m = re.search(r'\[([^\]]+)\]', title_part)
            if link_m:
                link_text = link_m.group(1).strip()
                # If the link text is short and looks like an acronym
                if len(link_text) < 30 and re.match(r'^[A-Z]', link_text):
                    acro_m2 = re.search(r'\(([A-Z][A-Z0-9\s&-]{1,20})\)', title_part)
                    if acro_m2:
                        project["acronym"] = acro_m2.group(1).strip()

        projects.append(project)

    return projects


# =============================================================================
# 2. BOOKS
# =============================================================================
def parse_books():
    """Parse books and chapters from llibres-i-capitols.md."""
    filepath = os.path.join(CONTENT_DIR, "llibres-i-capitols.md")
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()
    text = strip_frontmatter(text)

    books = []
    current_type = "chapter"

    # Split into blocks by double newline
    blocks = re.split(r'\n\n+', text)

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        # Check for type headings
        if re.match(r'\*\*Capítols de llibre', block):
            current_type = "chapter"
            continue
        if re.match(r'\*\*Proceedings', block):
            current_type = "proceedings"
            continue
        if re.match(r'\*\*Edicions', block):
            current_type = "edited-book"
            continue

        # Join lines
        entry_text = ' '.join(block.split('\n'))
        entry_text = clean_text(entry_text)

        if not entry_text or len(entry_text) < 10:
            continue

        # Extract year
        year = extract_year_from_text(entry_text)

        # Extract authors - text before (year)
        authors = ""
        m = re.match(r'^(.*?)\s*\(\d{4}\)', entry_text)
        if m:
            authors = m.group(1).strip().rstrip(',').rstrip('.')
            authors = clean_text(authors)

        # Extract title and URL
        title, url = "", ""
        # Try markdown link first
        link_m = re.search(r'\[([^\]]+)\]\(([^)]+)\)', entry_text)
        if link_m:
            title = clean_text(link_m.group(1))
            url = link_m.group(2).strip()
        else:
            # Try italic title
            m2 = re.search(r'\(\d{4}\)[.,]?\s*(.*?)(?:\.\s|$)', entry_text)
            if m2:
                title = clean_text(m2.group(1).strip().strip('*').strip('.'))

        # Extract book title (in italics after "Dins de" or "In:" or similar)
        book_title = ""
        bt_m = re.search(r'(?:Dins\s+de|In[:\s]|En[:\s])\s*(.*?\*([^*]+)\*)', entry_text)
        if bt_m:
            book_title = clean_text(bt_m.group(2))
        else:
            # Try any italic text after the title
            italics = re.findall(r'\*([^*]{5,})\*', entry_text)
            if italics:
                book_title = clean_text(italics[0])

        # Extract publisher - text after the last closing paren or after italic text
        publisher = ""
        # Try to find publisher after pages or after book title
        pub_m = re.search(r'(?:\)\.\s*|\)\s+)((?:Ed\.|Springer|Graó|Routledge|Waxmann|FECYT|Colciencias|IOS Press|Pegen|StudienVerlag|Didácticas Magisterio)[^.]*)', entry_text)
        if pub_m:
            publisher = clean_text(pub_m.group(1).strip().rstrip('.'))

        # Extract pages
        pages = ""
        pages_m = re.search(r'\(pp?\.\s*([\d]+-[\d]+)\)', entry_text)
        if pages_m:
            pages = pages_m.group(1)

        # Extract ISBN
        isbn = ""
        isbn_m = re.search(r'ISBN[:\s]*([\d-]+)', entry_text)
        if isbn_m:
            isbn = isbn_m.group(1)

        # Extract DOI
        doi = ""
        doi_m = re.search(r'(?:doi[:\s]*|https?://doi\.org/)(10\.\d+/[^\s]+)', entry_text, re.IGNORECASE)
        if doi_m:
            doi = doi_m.group(1)

        book = {
            "year": year,
            "authors": authors,
            "title": title,
            "book_title": book_title,
            "publisher": publisher,
            "pages": pages,
            "isbn": isbn,
            "doi": doi,
            "url": url,
            "type": current_type,
        }
        books.append(book)

    # Sort by year descending
    books.sort(key=lambda x: x["year"], reverse=True)
    return books


# =============================================================================
# 3. CONFERENCES
# =============================================================================
def parse_conferences():
    """Parse conference contributions from aportacions-a-congressos.md."""
    filepath = os.path.join(CONTENT_DIR, "aportacions-a-congressos.md")
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()
    text = strip_frontmatter(text)

    entries = []
    current_type = "plenary"

    # Split into blocks
    blocks = re.split(r'\n\n+', text)

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        # Check for type headings
        if re.match(r'\*\*Ponent convidat', block):
            current_type = "plenary"
            continue
        if re.match(r'\*\*Simposis i tallers', block):
            current_type = "symposium"
            continue
        if re.match(r'\*\*Comunicacions orals', block):
            current_type = "oral"
            continue
        if re.match(r'\*\*Pòsters', block):
            current_type = "poster"
            continue

        # Skip style-only blocks
        if block.startswith('[') and block.endswith('}') and 'style=' in block and len(block) < 100:
            continue

        # Join lines
        entry_text = ' '.join(block.split('\n'))
        entry_text = clean_text(entry_text)

        if not entry_text or len(entry_text) < 15:
            continue

        # Extract year
        year = extract_year_from_text(entry_text)
        if not year:
            continue

        # Extract authors - text before (year)
        authors = ""
        m = re.match(r'^(?:\[)?(.*?)\s*\(?\d{4}\)?', entry_text)
        if m:
            authors = m.group(1).strip().rstrip(',').rstrip('.')
            # Clean markdown link artifacts from authors
            authors = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', authors)
            authors = clean_text(authors)

        # Extract title - usually in italics after year
        title = ""
        url = ""

        # Try markdown link with italic
        link_m = re.search(r'\[\*([^*]+)\*\]\(([^)]+)\)', entry_text)
        if link_m:
            title = clean_text(link_m.group(1).strip('.'))
            url = link_m.group(2).strip()
        else:
            # Try markdown link
            link_m = re.search(r'\[([^\]]+)\]\(([^)]+)\)', entry_text)
            if link_m:
                title = clean_text(link_m.group(1).strip('*').strip('.'))
                url = link_m.group(2).strip()
            else:
                # Try italic text after year
                it_m = re.search(r'\(\d{4}\)[.,]?\s*\*([^*]+)\*', entry_text)
                if it_m:
                    title = clean_text(it_m.group(1).strip('.'))
                else:
                    # Plain text after year
                    pt_m = re.search(r'\(\d{4}\)[.,]?\s*(.+?)(?:\.\s|\*|$)', entry_text)
                    if pt_m:
                        title = clean_text(pt_m.group(1).strip('.'))

        # Extract conference name and location
        # Usually after the title, format: "Conference Name. Location (Country)."
        conference = ""
        location = ""

        # Find text after title (after the period following title)
        # The conference info is typically the last substantive part
        # Try to find location pattern: City (Country)
        loc_m = re.search(r'[.]\s*([A-ZÀ-Ý][^.]*?\([^)]+\))\s*\.?\s*$', entry_text)
        if loc_m:
            loc_text = loc_m.group(1).strip()
            # Split into conference and location
            # Location is usually "City (Country)" at the end
            city_m = re.search(r'^(.*?)\.\s*([A-ZÀ-Ý][\w\s,.-]+\([^)]+\))$', loc_text)
            if city_m:
                conference = clean_text(city_m.group(1).strip('.'))
                location = clean_text(city_m.group(2))
            else:
                # The whole thing might be "Conference. City (Country)"
                parts = loc_text.rsplit('.', 1)
                if len(parts) == 2:
                    conference = clean_text(parts[0].strip())
                    location = clean_text(parts[1].strip())
                else:
                    conference = clean_text(loc_text)

        entry = {
            "year": year,
            "authors": authors,
            "title": title,
            "conference": conference,
            "location": location,
            "type": current_type,
            "url": url,
        }
        entries.append(entry)

    # Sort by year descending
    entries.sort(key=lambda x: x["year"], reverse=True)
    return entries


# =============================================================================
# 4. TALKS
# =============================================================================
def parse_talks():
    """Parse invited talks from conferencies.md."""
    filepath = os.path.join(CONTENT_DIR, "conferencies.md")
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()
    text = strip_frontmatter(text)

    talks = []

    # Split into blocks
    blocks = re.split(r'\n\n+', text)

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        # Join lines
        entry_text = ' '.join(block.split('\n'))
        entry_text = clean_text(entry_text)

        if not entry_text or len(entry_text) < 15:
            continue

        year = extract_year_from_text(entry_text)
        if not year:
            continue

        # Extract title and URLs
        title = ""
        url = ""
        video_url = ""

        # Find all markdown links
        links = re.findall(r'\[([^\]]*)\]\(([^)]+)\)', entry_text)
        for link_text, link_url in links:
            lt = clean_text(link_text.strip('*').strip('.'))
            lu = link_url.strip()
            if 'youtube.com' in lu or 'youtu.be' in lu or 'vimeo.com' in lu:
                if not video_url:
                    video_url = lu
                if not title and lt:
                    title = lt
            else:
                if not url:
                    url = lu
                if not title and lt:
                    title = lt

        if not title:
            # Try italic text
            it_m = re.search(r'\*([^*]+)\*', entry_text)
            if it_m:
                title = clean_text(it_m.group(1).strip('.'))

        # Extract event and organizer
        # After the title link/text, there's usually: Event. Organizer
        event = ""
        organizer = ""

        # Get text after the last link or after the title
        after_title = entry_text
        # Remove everything up to and including the last '](...)'
        last_link_end = 0
        for m in re.finditer(r'\]\([^)]+\)', entry_text):
            last_link_end = m.end()
        if last_link_end > 0:
            after_title = entry_text[last_link_end:].strip().lstrip('.').lstrip(',').strip()
        else:
            # After italic title
            it_m = re.search(r'\*[^*]+\*[.)]?\s*(.*)', entry_text)
            if it_m:
                after_title = it_m.group(1).strip()

        # Split remaining text by periods to get event and organizer
        if after_title:
            parts = [p.strip() for p in after_title.split('.') if p.strip()]
            # Remove trailing year-like parts
            parts = [p for p in parts if p and not re.match(r'^\d{4}$', p)]
            if len(parts) >= 2:
                event = clean_text(parts[0])
                organizer = clean_text('. '.join(parts[1:]))
            elif len(parts) == 1:
                event = clean_text(parts[0])

        # Remove quotes from title
        title = title.strip('"').strip("'")

        talk = {
            "year": year,
            "title": title,
            "event": event,
            "organizer": organizer,
            "url": url,
            "video_url": video_url,
        }
        talks.append(talk)

    # Sort by year descending
    talks.sort(key=lambda x: x["year"], reverse=True)
    return talks


# =============================================================================
# 5. CONTRACTS
# =============================================================================
def parse_contracts():
    """Parse contracts from contractes-i-convenis.md."""
    filepath = os.path.join(CONTENT_DIR, "contractes-i-convenis.md")
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()
    text = strip_frontmatter(text)
    text = join_continuation_lines(text)

    contracts = []
    current_pi_role = "ip"

    # Split into blocks
    blocks = re.split(r'\n\n+', text)

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        # Section headings
        if re.match(r'\*\*Contractes i convenis', block):
            continue
        if re.match(r'\*\*IP:\s*Digna Couso', block):
            current_pi_role = "ip"
            continue
        if re.match(r'\*\*Altres IP', block):
            current_pi_role = "other-pi"
            continue

        # Parse entry - contracts start with a link or plain title, then fields
        # First, try to extract title+URL from the full block (links may span lines)
        title, url = extract_link(block)
        if not title or title.startswith('**Entitat') or title.startswith('**Durada'):
            # Try first line as plain text
            lines = block.split('\n')
            first_line = lines[0].strip()
            title = clean_text(first_line)
            url = ""

        if not title or title.startswith('**Entitat') or title.startswith('**Durada'):
            continue

        # Parse fields from rest of block
        full_block = block
        entity = ""
        budget = ""
        participants = ""
        duration = ""
        pi = ""
        code = ""

        # Funding entity
        m = re.search(r'\*\*Entitat\s+finançadora(?::\s*)?\*\*(?::?\s*)(.*?)(?=\*\*|\Z)', full_block, re.DOTALL)
        if m:
            entity = clean_text(m.group(1).strip())

        # Participants
        m = re.search(r'\*\*Entitats\s+[Pp]articipants?(?::\s*)?\*\*(?::?\s*)(.*?)(?=\*\*|\Z)', full_block, re.DOTALL)
        if m:
            participants = clean_text(m.group(1).strip())

        # Duration
        m = re.search(r'\*\*Durada(?::\s*)?\*\*(?::?\s*)(.*?)(?=\*\*|\Z)', full_block, re.DOTALL)
        if m:
            duration = clean_text(m.group(1).strip().rstrip('.'))

        # IP
        m = re.search(r'\*\*IP(?::\s*)?\*\*(?::?\s*)(.*?)(?=\*\*|\Z)', full_block, re.DOTALL)
        if m:
            pi = clean_text(m.group(1).strip().rstrip('.'))

        # Code - check for code pattern like CF612801: in the title
        code_m = re.search(r'([A-Z0-9][\w-]+):\s', title)
        if code_m:
            code = code_m.group(1)

        contract = {
            "code": code,
            "title": title,
            "entity": entity,
            "budget": budget,
            "duration": duration,
            "pi": pi,
            "pi_role": current_pi_role,
            "url": url,
        }
        contracts.append(contract)

    return contracts


# =============================================================================
# 6. THESES
# =============================================================================
def parse_theses():
    """Parse theses from direccio-de-treballs.md."""
    filepath = os.path.join(CONTENT_DIR, "direccio-de-treballs.md")
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()
    text = strip_frontmatter(text)

    theses = []
    current_type = "phd"
    current_status = "completed"

    # Split into blocks
    blocks = re.split(r'\n\n+', text)

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        # Section headings
        if re.match(r'\*\*Tesis doctorals en curs', block):
            current_type = "phd"
            current_status = "in-progress"
            continue
        if re.match(r'\*\*Tesis doctorals\s', block):
            current_type = "phd"
            current_status = "completed"
            continue
        if re.match(r'\*\*Treballs de Final de Màster', block):
            current_type = "master"
            current_status = "completed"
            continue
        if re.match(r'\*\*TFG', block):
            current_type = "tfg"
            current_status = "completed"
            continue

        # Join lines
        entry_text = ' '.join(block.split('\n'))
        entry_text = clean_text(entry_text)

        if not entry_text or len(entry_text) < 10:
            continue

        # Determine role
        role = "director"
        if 'Codirecció' in entry_text or 'codirecció' in entry_text:
            role = "co-director"

        # Extract year
        year = extract_year_from_text(entry_text)

        # Extract author - text before (year) or before the first period
        author = ""
        m = re.match(r'^([\w\s,.\'-]+?)\s*\(', entry_text)
        if m:
            author = m.group(1).strip().rstrip(',').rstrip('.')
            author = clean_text(author)

        # Extract title and URL
        title = ""
        url = ""
        link_m = re.search(r'\[([^\]]+)\]\(([^)]+)\)', entry_text)
        if link_m:
            title = clean_text(link_m.group(1))
            url = link_m.group(2).strip()
        else:
            # Try italic text
            it_m = re.search(r'\*([^*]+)\*', entry_text)
            if it_m:
                title = clean_text(it_m.group(1).strip('.'))
            else:
                # Plain text after year
                pt_m = re.search(r'\(\d{4}\)[.,]?\s*(.+?)(?:\.\s|UAB|$)', entry_text)
                if pt_m:
                    title = clean_text(pt_m.group(1).strip('.'))

        # Extract university
        university = ""
        uni_m = re.search(r'\.\s*(UAB|Universitat[^.(]*)', entry_text)
        if uni_m:
            university = clean_text(uni_m.group(1))
        elif 'UAB' in entry_text:
            university = "UAB"

        thesis = {
            "year": year,
            "author": author,
            "title": title,
            "type": current_type,
            "university": university,
            "role": role,
            "status": current_status,
            "url": url,
        }
        theses.append(thesis)

    # Sort by year descending
    theses.sort(key=lambda x: x["year"], reverse=True)
    return theses


# =============================================================================
# 7. MATERIALS
# =============================================================================
def parse_materials():
    """Parse teaching materials from material-didactic.md."""
    filepath = os.path.join(CONTENT_DIR, "material-didactic.md")
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()
    text = strip_frontmatter(text)

    materials = []

    # Split into blocks
    blocks = re.split(r'\n\n+', text)

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        # Join lines
        entry_text = ' '.join(block.split('\n'))
        entry_text = clean_text(entry_text)

        if not entry_text or len(entry_text) < 15:
            continue

        year = extract_year_from_text(entry_text)
        if not year:
            continue

        # Extract authors
        authors = ""
        m = re.match(r'^(.*?)\s*\(\d{4}\)', entry_text)
        if m:
            authors = m.group(1).strip().rstrip(',').rstrip('.')
            authors = clean_text(authors)

        # Extract title and URL
        title = ""
        url = ""
        link_m = re.search(r'\[([^\]]+)\]\(([^)]+)\)', entry_text)
        if link_m:
            title = clean_text(link_m.group(1))
            url = link_m.group(2).strip()
        else:
            # Text after year, before publisher
            pt_m = re.search(r'\(\d{4}\)[.,]?\s*(.+?)(?:\.\s|$)', entry_text)
            if pt_m:
                title = clean_text(pt_m.group(1).strip('.').strip('*').strip())

        # Extract publisher - usually after the title
        publisher = ""
        # Find text after the title/URL to end
        after_link = entry_text
        if link_m:
            after_link = entry_text[link_m.end():].strip().lstrip('.').strip()
        # Publisher patterns
        pub_parts = [p.strip() for p in after_link.split('.') if p.strip()]
        # Filter out version numbers and short fragments
        for part in pub_parts:
            part_clean = clean_text(part)
            if part_clean and len(part_clean) > 3 and not re.match(r'^Versió\s+\d', part_clean):
                if re.search(r'(?:Publicacions|CRECIM|DDD|Associació|Col·lecció|Dept|Generalitat|European|TEIDE|ABACUS|WOLTERS|Guías|Praxis)', part_clean):
                    publisher = part_clean
                    break

        material = {
            "year": year,
            "authors": authors,
            "title": title,
            "publisher": publisher,
            "url": url,
        }
        materials.append(material)

    # Sort by year descending
    materials.sort(key=lambda x: x["year"], reverse=True)
    return materials


# =============================================================================
# MAIN
# =============================================================================
PARSERS = {
    "projects": (parse_projects, "projects.json"),
    "books": (parse_books, "books.json"),
    "conferences": (parse_conferences, "conferences.json"),
    "talks": (parse_talks, "talks.json"),
    "contracts": (parse_contracts, "contracts.json"),
    "theses": (parse_theses, "theses.json"),
    "materials": (parse_materials, "materials.json"),
}


def main():
    parser = argparse.ArgumentParser(description="Parse content types to JSON")
    parser.add_argument("--type", required=True,
                        choices=list(PARSERS.keys()) + ["all"],
                        help="Content type to parse")
    args = parser.parse_args()

    os.makedirs(DATA_DIR, exist_ok=True)

    types_to_parse = list(PARSERS.keys()) if args.type == "all" else [args.type]

    for content_type in types_to_parse:
        parse_func, filename = PARSERS[content_type]
        try:
            data = parse_func()
            output_path = os.path.join(DATA_DIR, filename)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"{content_type}: {len(data)} entries -> {filename}")
        except Exception as e:
            print(f"ERROR parsing {content_type}: {e}", file=sys.stderr)
            raise


if __name__ == "__main__":
    main()
