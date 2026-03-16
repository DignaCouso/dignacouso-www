# Google Sheets CMS Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace manual Hugo markdown editing with a Google Sheets-based CMS that generates trilingual pages via Hugo content adapters.

**Architecture:** Data lives in JSON files under `data/`. Hugo content adapters (`_content.gotmpl`) read the JSON and generate pages for all 3 languages. A GitHub Action fetches data from Google Sheets, writes JSON, and commits — triggering a Netlify deploy.

**Tech Stack:** Hugo >= 0.145.0, Python 3 (migration/pipeline scripts), Google Sheets API, GitHub Actions, Netlify

**Spec:** `docs/superpowers/specs/2026-03-16-google-sheets-cms-design.md`

---

## Chunk 1: Prerequisites & Publications Pilot

This chunk sets up the infrastructure and migrates publications end-to-end as a pilot to validate the approach before doing the remaining content types.

### Task 1: Create netlify.toml and upgrade Hugo

**Files:**
- Create: `netlify.toml`

- [ ] **Step 1: Create netlify.toml**

```toml
[build]
  command = "hugo"
  publish = "public"

[build.environment]
  HUGO_VERSION = "0.145.0"
```

- [ ] **Step 2: Verify Hugo version locally**

Run: `hugo version`

If below 0.126.0, upgrade Hugo. On Ubuntu/Debian:

```bash
# Download the latest extended version
wget https://github.com/gohugoio/hugo/releases/download/v0.145.0/hugo_extended_0.145.0_linux-amd64.deb
sudo dpkg -i hugo_extended_0.145.0_linux-amd64.deb
hugo version
```

Expected: `hugo v0.145.0` or higher.

- [ ] **Step 3: Verify site still builds**

Run: `hugo --gc --minify`

Expected: Build succeeds with no errors.

- [ ] **Step 4: Commit**

```bash
git add netlify.toml
git commit -m "Add netlify.toml and pin Hugo version to 0.145.0"
```

---

### Task 2: Parse publications markdown into JSON

**Files:**
- Create: `scripts/parse_publications.py`
- Create: `data/publications.json`

The publications markdown (`content/ca/publicacions-cientifiques.md`) has this structure:
- Section headings as bold text: `**Articles en revistes indexades (JCR, SJR, SCOPUS):**`
- Each entry is a paragraph with: `Authors (year). [Title](URL). *Journal, Volume*(Issue), Pages`
- Some entries have DOIs embedded in URLs
- Sections map to types: `indexed-jcr`, `indexed-other`, `non-indexed`, `conference-derived`, `other`

- [ ] **Step 1: Write the parsing script**

Create `scripts/parse_publications.py`:

```python
#!/usr/bin/env python3
"""Parse publications markdown into JSON structure."""

import json
import re
import sys
from pathlib import Path


# Map section headings (from CA file) to type values
SECTION_MAP = {
    "Articles en revistes indexades (JCR, SJR, SCOPUS)": "indexed-jcr",
    "Articles en revistes indexades en altres índex": "indexed-other",
    "Articles en revistes no indexades amb avaluació externa": "non-indexed",
    "Publicacions derivades de congressos": "conference-derived",
    "Altres publicacions": "other",
}


def parse_publication_entry(text):
    """Parse a single publication entry from markdown text."""
    text = text.strip()
    if not text:
        return None

    entry = {
        "year": 0,
        "authors": "",
        "title": "",
        "journal": "",
        "volume": "",
        "issue": "",
        "pages": "",
        "doi": "",
        "url": "",
    }

    # Extract year: look for (YYYY) pattern
    year_match = re.search(r'\((\d{4})\)', text)
    if year_match:
        entry["year"] = int(year_match.group(1))

    # Extract authors: everything before the year pattern
    if year_match:
        authors = text[:year_match.start()].strip().rstrip(',').rstrip('.')
        entry["authors"] = authors

    # Extract URL from markdown link [Title](URL)
    link_match = re.search(r'\[([^\]]*)\]\(([^)]+)\)', text)
    if link_match:
        entry["title"] = link_match.group(1).strip().rstrip('.')
        entry["url"] = link_match.group(2).strip()
    else:
        # Title without link: text between year and journal (italic)
        after_year = text[year_match.end():] if year_match else text
        title_match = re.match(r'[.\s]*([^*]+?)(?:\.|$)', after_year)
        if title_match:
            entry["title"] = title_match.group(1).strip().rstrip('.')

    # Extract DOI from URL if present
    if entry["url"]:
        doi_match = re.search(r'(10\.\d{4,}/[^\s)]+)', entry["url"])
        if doi_match:
            entry["doi"] = doi_match.group(1)

    # Extract journal info from italic text *Journal, Volume*(Issue), Pages
    journal_match = re.search(r'\*([^*]+)\*', text)
    if journal_match:
        journal_text = journal_match.group(1)
        # Try to split journal name from volume
        parts = re.split(r',\s*(\d+)', journal_text, maxsplit=1)
        entry["journal"] = parts[0].strip().rstrip(',')
        if len(parts) > 1:
            entry["volume"] = parts[1].strip()

    # Extract issue in parentheses after journal
    after_journal = text[text.index('*') + len(journal_match.group(0)):] if journal_match else ""
    issue_match = re.search(r'\((\d+)\)', after_journal)
    if issue_match:
        entry["issue"] = issue_match.group(1)

    # Extract pages
    pages_match = re.search(r'(\d+[-–]\d+)', after_journal)
    if pages_match:
        entry["pages"] = pages_match.group(1).replace('–', '-')

    return entry


def parse_publications_file(filepath):
    """Parse the publications markdown file into a list of entries."""
    content = Path(filepath).read_text(encoding="utf-8")

    # Remove YAML front matter
    content = re.sub(r'^---\n.*?\n---\n', '', content, flags=re.DOTALL)

    publications = []
    current_type = "indexed-jcr"  # default

    # Split into paragraphs
    paragraphs = re.split(r'\n\n+', content)

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # Check if this is a section heading
        heading_match = re.match(r'\*\*([^*]+?)(?::)?\*\*', para)
        if heading_match:
            heading_text = heading_match.group(1).strip()
            for section_name, type_val in SECTION_MAP.items():
                if section_name.lower() in heading_text.lower():
                    current_type = type_val
                    break
            # If the paragraph is ONLY the heading, skip
            remaining = para[heading_match.end():].strip()
            if not remaining:
                continue
            para = remaining

        # Try to parse as a publication entry
        entry = parse_publication_entry(para)
        if entry and entry["year"] > 0:
            entry["type"] = current_type
            publications.append(entry)

    # Sort by year descending
    publications.sort(key=lambda x: x["year"], reverse=True)
    return publications


if __name__ == "__main__":
    input_file = sys.argv[1] if len(sys.argv) > 1 else "content/ca/publicacions-cientifiques.md"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "data/publications.json"

    publications = parse_publications_file(input_file)

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(publications, f, indent=2, ensure_ascii=False)

    print(f"Parsed {len(publications)} publications -> {output_file}")
```

- [ ] **Step 2: Run the parser**

```bash
mkdir -p data
python3 scripts/parse_publications.py content/ca/publicacions-cientifiques.md data/publications.json
```

Expected: `Parsed N publications -> data/publications.json` where N matches the number of publication entries in the source file.

- [ ] **Step 3: Manually review the JSON output**

Open `data/publications.json` and verify:
- Every publication from the source markdown is present
- Years, authors, titles, journals are correctly extracted
- URLs and DOIs are correctly captured
- Types match the section they appeared under
- Fix any parsing errors by adjusting the script and re-running

This step is critical — the markdown format is semi-structured and the parser may miss edge cases. Compare the entry count and spot-check several entries from each section.

- [ ] **Step 4: Commit**

```bash
git add scripts/parse_publications.py data/publications.json
git commit -m "Add publications parser and generate JSON data"
```

---

### Task 3: Build publications content adapter

**Files:**
- Create: `content/ca/publicacions-cientifiques/_content.gotmpl`
- Create: `content/en/publicacions-cientifiques/_content.gotmpl` (identical copy)
- Create: `content/es/publicacions-cientifiques/_content.gotmpl` (identical copy)
- Delete: `content/ca/publicacions-cientifiques.md`
- Delete: `content/en/publicacions-cientifiques.en.md`
- Delete: `content/es/publicacions-cientifiques.es.md`

**Important:** The existing `.md` files must be deleted before creating the directory of the same base name. A file and directory cannot coexist.

- [ ] **Step 1: Delete old markdown files**

```bash
rm content/ca/publicacions-cientifiques.md
rm content/en/publicacions-cientifiques.en.md
rm content/es/publicacions-cientifiques.es.md
```

- [ ] **Step 2: Create directory structure**

```bash
mkdir -p content/ca/publicacions-cientifiques
mkdir -p content/en/publicacions-cientifiques
mkdir -p content/es/publicacions-cientifiques
```

- [ ] **Step 3: Write the content adapter**

Create `content/ca/publicacions-cientifiques/_content.gotmpl`:

```go-html-template
{{/* Publications content adapter - identical across all language dirs */}}
{{ $lang := .Site.Language.Lang }}
{{ $data := index .Site.Data "publications" }}

{{/* Translated titles */}}
{{ $titles := dict "ca" "Publicacions Científiques" "es" "Publicaciones Científicas" "en" "Scientific Publications" }}

{{/* Translated slugs (CA uses directory name, no slug needed) */}}
{{ $slugs := dict "ca" "" "es" "publicaciones-cientificas" "en" "scientific-publications" }}

{{/* Section headings by type */}}
{{ $headings := dict
  "indexed-jcr" (dict
    "ca" "Articles en revistes indexades (JCR, SJR, SCOPUS)"
    "es" "Artículos en revistas indexadas (JCR, SJR, SCOPUS)"
    "en" "Publications on journals with impact factor (JCR, SJR, SCOPUS)")
  "indexed-other" (dict
    "ca" "Articles en revistes indexades en altres índex"
    "es" "Artículos en revistas indexadas en otros índices"
    "en" "Publications on journals with impact factor in other index")
  "non-indexed" (dict
    "ca" "Articles en revistes no indexades amb avaluació externa"
    "es" "Artículos en revistas no indexadas con evaluación externa"
    "en" "Publications on journals without impact factor but with external peer review")
  "conference-derived" (dict
    "ca" "Publicacions derivades de congressos"
    "es" "Publicaciones derivadas de congresos"
    "en" "Publications derived from conferences")
  "other" (dict
    "ca" "Altres publicacions"
    "es" "Otras publicaciones"
    "en" "Other publications")
}}

{{/* Section order */}}
{{ $typeOrder := slice "indexed-jcr" "indexed-other" "non-indexed" "conference-derived" "other" }}

{{/* Build content */}}
{{ $content := "" }}

{{/* RIS download link */}}
{{ $risLabel := dict "ca" "Descarrega totes les publicacions en format RIS (Zotero)" "es" "Descarga todas las publicaciones en formato RIS (Zotero)" "en" "Download all publications in RIS format (Zotero)" }}
{{ $content = printf "%s[%s](/publications/couso-publications.ris)\n\n" $content (index $risLabel $lang) }}

{{ range $type := $typeOrder }}
  {{ $items := where $data "type" $type }}
  {{ if $items }}
    {{ $heading := index (index $headings $type) $lang }}
    {{ $content = printf "%s**%s:**\n\n" $content $heading }}
    {{ range $items }}
      {{/* Format: Authors (Year). [Title](URL). *Journal, Volume*(Issue), Pages */}}
      {{ $entry := printf "%s (%d). " .authors .year }}
      {{ if .url }}
        {{ $entry = printf "%s[%s](%s). " $entry .title .url }}
      {{ else }}
        {{ $entry = printf "%s%s. " $entry .title }}
      {{ end }}
      {{ if .journal }}
        {{ $entry = printf "%s*%s" $entry .journal }}
        {{ if .volume }}
          {{ $entry = printf "%s, %s" $entry .volume }}
        {{ end }}
        {{ $entry = printf "%s*" $entry }}
        {{ if .issue }}
          {{ $entry = printf "%s(%s)" $entry .issue }}
        {{ end }}
        {{ if .pages }}
          {{ $entry = printf "%s, %s" $entry .pages }}
        {{ end }}
      {{ end }}
      {{ $content = printf "%s%s\n\n" $content $entry }}
    {{ end }}
  {{ end }}
{{ end }}

{{/* Build page */}}
{{ $page := dict
  "content" (dict "mediaType" "text/markdown" "value" $content)
  "path" "publicacions-cientifiques"
  "title" (index $titles $lang)
  "menus" (dict "main" (dict "weight" 4))
}}

{{/* Add slug for non-CA languages */}}
{{ $slug := index $slugs $lang }}
{{ if $slug }}
  {{ $page = merge $page (dict "slug" $slug) }}
{{ end }}

{{ $.AddPage $page }}
```

- [ ] **Step 4: Copy adapter to en and es directories**

```bash
cp content/ca/publicacions-cientifiques/_content.gotmpl content/en/publicacions-cientifiques/_content.gotmpl
cp content/ca/publicacions-cientifiques/_content.gotmpl content/es/publicacions-cientifiques/_content.gotmpl
```

- [ ] **Step 5: Build and verify**

```bash
hugo server
```

Open the site in a browser and compare the publications page across all 3 languages:
- CA: `http://localhost:1313/publicacions-cientifiques/` — check content matches original
- EN: `http://localhost:1313/en/scientific-publications/` — check URL and content
- ES: `http://localhost:1313/es/publicaciones-cientificas/` — check URL and content
- Check navigation menu still shows the publications link in the correct position

If the build fails or output looks wrong, debug the adapter template and fix.

- [ ] **Step 6: Commit**

```bash
git add content/ca/publicacions-cientifiques/ content/en/publicacions-cientifiques/ content/es/publicacions-cientifiques/ data/publications.json
git add -u  # stages deleted .md files
git commit -m "Migrate publications to content adapter with JSON data"
```

---

## Chunk 2: Remaining Content Types Migration

Repeat the parse + adapter pattern for all 7 remaining content types. Each task follows the same structure: parse markdown → JSON, build adapter, verify, commit.

### Task 4: Parse all remaining content types into JSON

**Files:**
- Create: `scripts/parse_content.py` (unified parser for all remaining types)
- Create: `data/projects.json`
- Create: `data/books.json`
- Create: `data/conferences.json`
- Create: `data/talks.json`
- Create: `data/contracts.json`
- Create: `data/theses.json`
- Create: `data/materials.json`

Each content type has a different markdown format. The parser needs separate logic per type.

**Projects format** (`projectes-de-recerca.md`):
- Section headings: `**Projectes R+D+i competitius**`, `**Xarxes de recerca I+D**`
- PI role headings: `**IP: Digna Couso**`, `**IP Nacional**`, `**Altres IP**`
- Entry format: `**CODE:** [Title](URL)\` then `**Entitat Finançadora:** ...\` etc.

**Books format** (`llibres-i-capitols.md`):
- Section headings: `**Capítols de llibre:**`, `**Proceedings:**`, `**Edicions:**`
- Entry format: `Authors (Year). [Title](URL). Dins de/In ... *Book Title* (pp. X-Y). Publisher`

**Conference contributions format** (`aportacions-a-congressos.md`):
- Section headings: `**Ponent convidat...**`, `**Simposis i tallers**`, `**Comunicacions orals**`, `**Pòsters**`
- Entry format: `Authors (Year). Title. Conference, Location. Type.`

**Talks format** (`conferencies.md`):
- Flat list, no sections
- Entry format: `Author (Year). [Title](URL). Event/Organizer.`

**Contracts format** (`contractes-i-convenis.md`):
- PI role headings: `**IP: Digna Couso:**`, `**Altres IP:**`
- Entry format: `[Title](URL)\` then `**Entitat finançadora:** ...\` etc. (similar to projects)

**Theses format** (`direccio-de-treballs.md`):
- Section headings: `**Tesis doctorals :**`, `**Tesis doctorals en curs:**`, `**Treballs de Final de Màster...**`
- Entry format: `Author (Year). [Title](URL). University (Codirecció: Name)`

**Materials format** (`material-didactic.md`):
- Flat list, no sections
- Entry format: `Authors (Year). [Title](URL). Publisher.`

- [ ] **Step 1: Write the unified parser**

Create `scripts/parse_content.py` — a Python script with a separate parsing function for each content type. Each function reads the CA markdown file and outputs the corresponding JSON.

The script should:
1. Accept a `--type` argument: `projects`, `books`, `conferences`, `talks`, `contracts`, `theses`, `materials`, or `all`
2. Read from the CA content file (the authoritative source)
3. Output JSON to `data/<type>.json`
4. Print a summary of entries parsed per section/type

Use the same pattern as `parse_publications.py`: regex-based extraction, manual review expected.

- [ ] **Step 2: Run parser for each type**

```bash
python3 scripts/parse_content.py --type all
```

Expected: JSON files created in `data/` with correct entry counts for each type.

- [ ] **Step 3: Manually review all JSON files**

For each JSON file:
- Count entries and compare to source markdown
- Spot-check several entries for correct field extraction
- Verify type/section/role assignments are correct
- Fix parsing issues and re-run

This is the most labor-intensive step. Budget time for manual review and script fixes.

- [ ] **Step 4: Commit**

```bash
git add scripts/parse_content.py data/
git commit -m "Parse all content types into JSON data files"
```

---

### Task 5: Build content adapters for projects

**Files:**
- Create: `content/{ca,en,es}/projectes-de-recerca/_content.gotmpl`
- Delete: `content/ca/projectes-de-recerca.md`
- Delete: `content/en/projectes-de-recerca.en.md`
- Delete: `content/es/projectes-de-recerca.es.md`

- [ ] **Step 1: Delete old markdown files**

```bash
rm content/ca/projectes-de-recerca.md
rm content/en/projectes-de-recerca.en.md
rm content/es/projectes-de-recerca.es.md
```

- [ ] **Step 2: Create directories**

```bash
mkdir -p content/{ca,en,es}/projectes-de-recerca
```

- [ ] **Step 3: Write the content adapter**

Create `content/ca/projectes-de-recerca/_content.gotmpl`. Follow the same pattern as the publications adapter but with:

- Titles: `"ca" "Projectes de recerca"`, `"es" "Proyectos de investigación"`, `"en" "Research Projects"`
- Slugs: `"es" "proyectos-de-investigacion"`, `"en" "research-projects"`
- Menu weight: 2
- Section headings for `competitive` and `networks` sections
- PI role subheadings: `IP: Digna Couso` / `IP Nacional` / `Altres IP`
- Field labels: `Entitat Finançadora`/`Entidad Financiadora`/`Funding Entity`, `Durada`/`Duración`/`Duration`, etc.
- Entry format: `**CODE:** [Title](URL)\ **Label:** Value\` etc.

- [ ] **Step 4: Copy adapter to en and es**

```bash
cp content/ca/projectes-de-recerca/_content.gotmpl content/en/projectes-de-recerca/_content.gotmpl
cp content/ca/projectes-de-recerca/_content.gotmpl content/es/projectes-de-recerca/_content.gotmpl
```

- [ ] **Step 5: Build and verify**

```bash
hugo server
```

Check all 3 language URLs. Verify menu position, content, and formatting.

- [ ] **Step 6: Commit**

```bash
git add content/{ca,en,es}/projectes-de-recerca/ -u
git commit -m "Migrate research projects to content adapter"
```

---

### Task 6: Build content adapters for books

**Files:**
- Create: `content/{ca,en,es}/llibres-i-capitols/_content.gotmpl`
- Delete: `content/{ca,en,es}/llibres-i-capitols*.md`

Follow same pattern. Key differences:
- Titles: `"ca" "Llibres i capítols"`, `"es" "Libros y capítulos"`, `"en" "Books and chapters"`
- Slugs: `"es" "libros-y-capitulos"`, `"en" "books-and-chapters"`
- Menu weight: 5
- Section headings for `chapter`, `book`, `edited-book`, `proceedings`
- Entry format: `Authors (Year). [Title](URL). Dins de/Dentro de/In *Book* (pp. X-Y). Publisher`

- [ ] **Step 1-6:** Same sequence as Task 5 (delete, mkdir, write adapter, copy, verify, commit)

---

### Task 7: Build content adapters for conference contributions

**Files:**
- Create: `content/{ca,en,es}/aportacions-a-congressos/_content.gotmpl`
- Delete: `content/{ca,en,es}/aportacions-a-congressos*.md` and `content/{en,es}/aportaciones-a-congresos*.md`

Key differences:
- Titles: `"ca" "Aportacions a congressos"`, `"es" "Aportaciones a congresos"`, `"en" "Conference contributions"`
- Slugs: `"es" "aportaciones-a-congresos"`, `"en" "conference-contributions"`
- Menu weight: 6
- Section headings for `plenary`, `symposium`, `oral`, `poster`

**Note:** The ES and EN filenames differ from CA (`aportaciones-a-congresos` vs `aportacions-a-congressos`). Delete all variants.

- [ ] **Step 1-6:** Same sequence as Task 5

---

### Task 8: Build content adapters for invited talks

**Files:**
- Create: `content/{ca,en,es}/conferencies/_content.gotmpl`
- Delete: `content/{ca,en,es}/conferencies*.md`

Key differences:
- Titles: `"ca" "Conferències"`, `"es" "Conferencias"`, `"en" "Conferences"`
- Slugs: `"es" "conferencias"`, `"en" "conferences"`
- Menu weight: 11
- No section headings — flat list
- Entry format: `Author (Year). [Title](URL). Event.`

- [ ] **Step 1-6:** Same sequence as Task 5

---

### Task 9: Build content adapters for contracts

**Files:**
- Create: `content/{ca,en,es}/contractes-i-convenis/_content.gotmpl`
- Delete: `content/{ca,en,es}/contractes-i-convenis*.md`

Key differences:
- Titles: `"ca" "Contractes i convenis"`, `"es" "Contratos y convenios"`, `"en" "Contracts and agreements"`
- Slugs: `"es" "contratos-y-convenios"`, `"en" "contracts-and-agreements"`
- Menu weight: 3
- PI role subheadings (same as projects)
- Field labels (same as projects)

- [ ] **Step 1-6:** Same sequence as Task 5

---

### Task 10: Build content adapters for theses

**Files:**
- Create: `content/{ca,en,es}/direccio-de-treballs/_content.gotmpl`
- Delete: `content/{ca,en,es}/direccio-de-treballs*.md`

Key differences:
- Titles: `"ca" "Direcció de treballs"`, `"es" "Dirección de trabajos"`, `"en" "Doctoral thesis supervision"`
- Slugs: `"es" "direccion-de-trabajos"`, `"en" "doctoral-thesis-supervision"`
- Menu weight: 9
- Section headings for `phd` (completed), `phd` (in-progress), `master`, `tfg`
- Entry format: `Author (Year). [Title](URL). University (Codirecció: Name)`

- [ ] **Step 1-6:** Same sequence as Task 5

---

### Task 11: Build content adapters for teaching materials

**Files:**
- Create: `content/{ca,en,es}/material-didactic/_content.gotmpl`
- Delete: `content/{ca,en,es}/material-didactic*.md`

Key differences:
- Titles: `"ca" "Material didàctic"`, `"es" "Material didáctico"`, `"en" "Teaching materials"`
- Slugs: `"es" "material-didactico"`, `"en" "teaching-materials"`
- Menu weight: 8
- No section headings — flat list
- Clean up any HTML style artifacts (`style="font-family:..."`) from the original markdown

- [ ] **Step 1-6:** Same sequence as Task 5

---

### Task 12: Full site verification

- [ ] **Step 1: Build the full site**

```bash
hugo --gc --minify
```

Expected: Build succeeds with no errors or warnings about page collisions.

- [ ] **Step 2: Compare all pages**

Run `hugo server` and manually check every migrated page in all 3 languages:
- Content is complete and correctly formatted
- Navigation menu order matches the original site
- URLs match the original site (check CA, EN, ES slugs)
- No broken links within the site
- Static pages (biography, training, acknowledgments, homepage) still work

- [ ] **Step 3: Check for leftover files**

```bash
# Verify no old content markdown files remain for migrated types
ls content/ca/*.md content/en/*.md content/es/*.md
```

Expected: Only static content files remain (ressenya-biografica, formacio, reconeixements, _index).

- [ ] **Step 4: Commit any final fixes**

```bash
git add -A
git commit -m "Complete content migration to JSON + content adapters"
```

---

## Chunk 3: Publish Pipeline

### Task 13: Create the sheet-to-JSON conversion script

**Files:**
- Create: `scripts/sheet_to_json.py`

This script is used by the GitHub Action to fetch Google Sheet data and write JSON files.

- [ ] **Step 1: Write the conversion script**

Create `scripts/sheet_to_json.py`:

```python
#!/usr/bin/env python3
"""Fetch Google Sheet tabs and write JSON data files."""

import json
import os
import sys
from pathlib import Path

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

# Map sheet tab names to JSON filenames and required fields
TABS = {
    "Publications": {
        "file": "data/publications.json",
        "required": ["year", "authors", "title"],
        "enums": {"type": ["indexed-jcr", "indexed-other", "non-indexed", "conference-derived", "other"]},
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
        "enums": {"type": ["chapter", "book", "edited-book", "proceedings"]},
    },
    "Conferences": {
        "file": "data/conferences.json",
        "required": ["year", "authors", "title"],
        "enums": {"type": ["plenary", "symposium", "oral", "poster"]},
    },
    "Talks": {
        "file": "data/talks.json",
        "required": ["year", "title"],
        "enums": {},
    },
    "Contracts": {
        "file": "data/contracts.json",
        "required": ["title"],
        "enums": {"pi_role": ["ip", "other-pi"]},
    },
    "Theses": {
        "file": "data/theses.json",
        "required": ["year", "author", "title"],
        "enums": {
            "type": ["phd", "master", "tfg"],
            "status": ["completed", "in-progress"],
        },
    },
    "Materials": {
        "file": "data/materials.json",
        "required": ["year", "title"],
        "enums": {},
    },
}


def get_sheet_data(service, sheet_id, tab_name):
    """Fetch all rows from a sheet tab."""
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=f"{tab_name}!A:Z"
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
            value = row[i].strip() if i < len(row) else ""
            # Convert year to int
            if header == "year" and value:
                try:
                    value = int(value)
                except ValueError:
                    pass
            entry[header] = value
        entries.append(entry)
    return entries


def validate_entries(entries, tab_config, tab_name):
    """Validate entries against required fields and enums."""
    errors = []
    for i, entry in enumerate(entries):
        row_num = i + 2  # 1-indexed + header row
        for field in tab_config["required"]:
            if not entry.get(field):
                errors.append(f"{tab_name} row {row_num}: missing required field '{field}'")
        for field, allowed in tab_config["enums"].items():
            val = entry.get(field, "")
            if val and val not in allowed:
                errors.append(f"{tab_name} row {row_num}: '{field}' value '{val}' not in {allowed}")
    return errors


def main():
    # Auth
    creds_json = os.environ.get("GOOGLE_SHEETS_KEY")
    sheet_id = os.environ.get("GOOGLE_SHEET_ID")
    if not creds_json or not sheet_id:
        print("Error: GOOGLE_SHEETS_KEY and GOOGLE_SHEET_ID env vars required")
        sys.exit(1)

    creds_info = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    service = build("sheets", "v4", credentials=creds)

    all_errors = []
    for tab_name, config in TABS.items():
        print(f"Fetching {tab_name}...")
        entries = get_sheet_data(service, sheet_id, tab_name)
        errors = validate_entries(entries, config, tab_name)
        all_errors.extend(errors)

        output_path = Path(config["file"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2, ensure_ascii=False)
        print(f"  {len(entries)} entries -> {config['file']}")

    if all_errors:
        print("\nValidation errors:")
        for err in all_errors:
            print(f"  - {err}")
        sys.exit(1)

    print("\nAll tabs processed successfully.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Add Python dependencies**

Create `scripts/requirements.txt`:

```
google-auth>=2.0.0
google-api-python-client>=2.0.0
```

- [ ] **Step 3: Commit**

```bash
git add scripts/sheet_to_json.py scripts/requirements.txt
git commit -m "Add Google Sheets to JSON conversion script"
```

---

### Task 14: Create GitHub Action workflow

**Files:**
- Create: `.github/workflows/publish.yml`

- [ ] **Step 1: Write the workflow**

Create `.github/workflows/publish.yml`:

```yaml
name: Publish from Google Sheets

on:
  repository_dispatch:
    types: [publish]
  workflow_dispatch:

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: pip install -r scripts/requirements.txt

      - name: Fetch sheet data and generate JSON
        env:
          GOOGLE_SHEETS_KEY: ${{ secrets.GOOGLE_SHEETS_KEY }}
          GOOGLE_SHEET_ID: ${{ secrets.GOOGLE_SHEET_ID }}
        run: python3 scripts/sheet_to_json.py

      - name: Setup Hugo
        uses: peaceiris/actions-hugo@v3
        with:
          hugo-version: "0.145.0"
          extended: true

      - name: Verify Hugo build
        run: hugo --gc --minify

      - name: Check for changes
        id: changes
        run: |
          if git diff --quiet data/; then
            echo "changed=false" >> $GITHUB_OUTPUT
          else
            echo "changed=true" >> $GITHUB_OUTPUT
          fi

      - name: Commit and push
        if: steps.changes.outputs.changed == 'true'
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/
          git commit -m "Update content from Google Sheets"
          git push
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/publish.yml
git commit -m "Add GitHub Action for Google Sheets publish pipeline"
```

---

### Task 15: Generate CSVs for Google Sheet import

**Files:**
- Create: `scripts/json_to_csv.py`

- [ ] **Step 1: Write CSV export script**

Create `scripts/json_to_csv.py`:

```python
#!/usr/bin/env python3
"""Convert JSON data files to CSV for Google Sheets import."""

import csv
import json
import sys
from pathlib import Path

DATA_DIR = Path("data")
OUTPUT_DIR = Path("sheets_csv")


def json_to_csv(json_file, csv_file):
    """Convert a JSON array file to CSV."""
    with open(json_file, encoding="utf-8") as f:
        data = json.load(f)
    if not data:
        print(f"  Skipping {json_file} (empty)")
        return

    fieldnames = list(data[0].keys())
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    print(f"  {len(data)} entries -> {csv_file}")


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    for json_file in sorted(DATA_DIR.glob("*.json")):
        csv_file = OUTPUT_DIR / f"{json_file.stem}.csv"
        json_to_csv(json_file, csv_file)
    print(f"\nCSV files ready in {OUTPUT_DIR}/")
    print("Import each CSV as a separate tab in Google Sheets.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run CSV export**

```bash
python3 scripts/json_to_csv.py
```

Expected: CSV files in `sheets_csv/` directory, one per content type.

- [ ] **Step 3: Import into Google Sheets**

Manual steps (done once):
1. Create a new Google Sheet
2. For each CSV: File > Import > Upload > select CSV > "Insert new sheet"
3. Rename each tab to match: Publications, Projects, Books, Conferences, Talks, Contracts, Theses, Materials
4. Freeze the header row in each tab (View > Freeze > 1 row)
5. Add data validation dropdowns for type/section/role columns
6. Add conditional formatting to highlight empty required fields

- [ ] **Step 4: Commit script (don't commit CSVs)**

```bash
git add scripts/json_to_csv.py
echo "sheets_csv/" >> .gitignore
git add .gitignore
git commit -m "Add JSON to CSV export script for sheet import"
```

---

### Task 16: Set up Google Apps Script publish button

This is done manually in the Google Sheet, not in the codebase.

- [ ] **Step 1: Set up GitHub secrets**

In the GitHub repo settings (Settings > Secrets and variables > Actions), add:
- `GOOGLE_SHEETS_KEY`: The service account JSON key (full contents)
- `GOOGLE_SHEET_ID`: The sheet ID from the Google Sheet URL

- [ ] **Step 2: Create a GitHub personal access token**

Create a fine-grained PAT with `contents: write` permission on the repo. This token is used by the Apps Script to trigger the workflow.

- [ ] **Step 3: Add Apps Script to the sheet**

In the Google Sheet: Extensions > Apps Script. Paste:

```javascript
function publish() {
  var token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  var response = UrlFetchApp.fetch(
    'https://api.github.com/repos/DignaCouso/dignacouso-www/dispatches',
    {
      method: 'post',
      headers: {
        'Authorization': 'token ' + token,
        'Accept': 'application/vnd.github.v3+json'
      },
      payload: JSON.stringify({ event_type: 'publish' }),
      muteHttpExceptions: true
    }
  );
  if (response.getResponseCode() === 204) {
    SpreadsheetApp.getUi().alert('Publishing! The site will update in ~2 minutes.');
  } else {
    SpreadsheetApp.getUi().alert('Error: ' + response.getContentText());
  }
}

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Website')
    .addItem('Publish', 'publish')
    .addToUi();
}
```

- [ ] **Step 4: Store the GitHub token**

In Apps Script: Project Settings > Script Properties > Add property:
- Property: `GITHUB_TOKEN`
- Value: The personal access token from step 2

- [ ] **Step 5: Test the publish button**

1. Reload the Google Sheet (the "Website" menu should appear)
2. Click "Website" > "Publish"
3. Check GitHub Actions to see the workflow run
4. Verify the site updates on Netlify

---

### Task 17: Update RIS generation script

**Files:**
- Modify: `scripts/generate_ris.py`

- [ ] **Step 1: Update script to read from JSON**

Modify `scripts/generate_ris.py` to read from `data/publications.json` instead of parsing markdown. The RIS output format should remain the same.

- [ ] **Step 2: Regenerate RIS file**

```bash
python3 scripts/generate_ris.py
```

Verify `static/publications/couso-publications.ris` is generated correctly.

- [ ] **Step 3: Commit**

```bash
git add scripts/generate_ris.py static/publications/couso-publications.ris
git commit -m "Update RIS generator to read from JSON data"
```

---

### Task 18: Final end-to-end test

- [ ] **Step 1: Make a test edit in the Google Sheet**

Add a dummy publication entry to the Publications tab.

- [ ] **Step 2: Click Publish**

Use the Website > Publish menu item.

- [ ] **Step 3: Verify the full pipeline**

1. Check GitHub Actions: workflow should run and succeed
2. Check the repo: `data/publications.json` should have the new entry
3. Check the live site: the dummy publication should appear on all 3 language pages

- [ ] **Step 4: Remove the test entry**

Delete the dummy row from the sheet, click Publish again, verify it's removed from the site.

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "Complete Google Sheets CMS pipeline setup"
```
