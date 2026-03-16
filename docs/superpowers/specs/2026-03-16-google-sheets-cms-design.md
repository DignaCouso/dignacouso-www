# Google Sheets CMS for Academic Website

## Summary

Replace manual Hugo markdown editing with a Google Sheets-based content management system. Dr. Digna Couso maintains her academic data (publications, projects, etc.) in a Google Sheet. A publish button triggers a GitHub Action that converts the sheet data to JSON files, which Hugo content adapters use to generate trilingual pages (ca/es/en) at build time.

## Context

- **Site:** dignacouso.me — trilingual (ca/es/en) academic portfolio built with Hugo + Hyde theme, deployed on Netlify
- **Problem:** The site owner is not comfortable editing Hugo markdown files directly
- **Constraint:** She works from one Windows computer with no technical tools installed (no Git, Python, etc.). She needs full autonomy — no technical help required to publish
- **Content update pattern:** All data available at once when adding entries; updates all content types

## Content Types

### Managed by Google Sheets (frequently updated)

| Content Type | Current Files | JSON Data File |
|---|---|---|
| Publications | `publicacions-cientifiques.*` | `data/publications.json` |
| Research Projects | `projectes-de-recerca.*` | `data/projects.json` |
| Books and Chapters | `llibres-i-capitols.*` | `data/books.json` |
| Conference Contributions | `aportacions-a-congressos.*` | `data/conferences.json` |
| Invited Talks | `conferencies.*` | `data/talks.json` |
| Contracts and Agreements | `contractes-i-convenis.*` | `data/contracts.json` |
| Thesis Supervision | `direccio-de-treballs.*` | `data/theses.json` |
| Teaching Materials | `material-didactic.*` | `data/materials.json` |

### Manually edited (rarely change)

- Biography (`ressenya-biografica`)
- Training/Education (`formacio`)
- Acknowledgments (`reconeixements`)
- Homepage (`_index`)

## Data Structure

All data is language-independent. Translations of section headings and field labels are handled in Hugo content adapter templates.

### publications.json

```json
[
  {
    "year": 2024,
    "authors": "Couso, D.; Smith, J.",
    "title": "Some title here",
    "journal": "Science Education",
    "volume": "45",
    "issue": "2",
    "pages": "12-30",
    "doi": "10.1000/xyz",
    "url": "",
    "type": "indexed-jcr"
  }
]
```

Types: `indexed-jcr`, `indexed-other`, `non-indexed`, `conference-derived`, `other`

### projects.json

```json
[
  {
    "code": "PGC2018-096581-B-C21",
    "acronym": "STEAM4U",
    "title": "Raising students' perceived self-efficacy...",
    "funding_entity": "European Commission",
    "budget": "170.940\u20ac",
    "duration": "2016-2019",
    "participants": "Thomas More (Belgium), ...",
    "pi": "Digna Couso",
    "pi_role": "ip",
    "url": "https://www.crecim.cat/ca/projecte/...",
    "section": "competitive"
  }
]
```

Sections: `competitive`, `networks`. PI roles: `ip`, `ip-national`, `other-pi`

### books.json

```json
[
  {
    "year": 2020,
    "authors": "Couso, D.",
    "title": "Chapter title",
    "book_title": "Book title",
    "publisher": "Springer",
    "pages": "45-67",
    "isbn": "",
    "doi": "",
    "url": "",
    "type": "chapter"
  }
]
```

Types: `chapter`, `book`, `edited-book`, `proceedings`

### conferences.json

```json
[
  {
    "year": 2023,
    "authors": "Couso, D.",
    "title": "Presentation title",
    "conference": "ESERA 2023",
    "location": "Cappadocia, Turkey",
    "type": "oral",
    "url": ""
  }
]
```

Types: `plenary`, `symposium`, `oral`, `poster`

### talks.json

```json
[
  {
    "year": 2023,
    "title": "Talk title",
    "event": "Event name",
    "organizer": "Institution",
    "url": "",
    "video_url": ""
  }
]
```

### contracts.json

```json
[
  {
    "code": "C-12345",
    "title": "Contract title",
    "entity": "Fundacio La Caixa",
    "budget": "50.000\u20ac",
    "duration": "2018-2019",
    "pi": "Digna Couso",
    "pi_role": "ip",
    "url": ""
  }
]
```

PI roles: `ip`, `other-pi`

### theses.json

```json
[
  {
    "year": 2021,
    "author": "Student Name",
    "title": "Thesis title",
    "type": "phd",
    "university": "UAB",
    "role": "director",
    "status": "completed",
    "url": ""
  }
]
```

Types: `phd`, `master`, `tfg`. Status: `completed`, `in-progress`

### materials.json

```json
[
  {
    "year": 2020,
    "authors": "Couso, D.",
    "title": "Material title",
    "publisher": "Publisher",
    "url": ""
  }
]
```

## Hugo Content Adapters

Each content type gets a `_content.gotmpl` file that reads its JSON and generates trilingual pages.

### File structure

```
content/
├── publications/
│   ├── _content.gotmpl
│   └── _index.md
├── projects/
│   ├── _content.gotmpl
│   └── _index.md
├── books/
│   ├── _content.gotmpl
│   └── _index.md
├── conferences/
│   ├── _content.gotmpl
│   └── _index.md
├── talks/
│   ├── _content.gotmpl
│   └── _index.md
├── contracts/
│   ├── _content.gotmpl
│   └── _index.md
├── theses/
│   ├── _content.gotmpl
│   └── _index.md
└── materials/
    ├── _content.gotmpl
    └── _index.md
```

### Adapter pattern

Each adapter follows this structure:

1. Call `EnableAllLanguages` to generate pages for ca/es/en from a single template
2. Read data from `site.Data` (the JSON files)
3. Use translation dicts for section headings and field labels
4. Group entries by type/section
5. Generate markdown content string
6. Call `AddPage` with the content and translated title

### Translation approach

All translations are defined in the adapter templates as Go template dicts. Example:

```go-html-template
{{ $headings := dict
  "indexed-jcr" (dict
    "ca" "Articles en revistes indexades (JCR, SJR, SCOPUS)"
    "es" "Articulos en revistas indexadas (JCR, SJR, SCOPUS)"
    "en" "Publications on journals with impact factor (JCR, SJR, SCOPUS)"
  )
}}
```

Field labels (e.g., "Funding Entity" / "Entitat Finançadora" / "Entidad Financiadora") follow the same pattern.

## Publish Pipeline

### Flow

1. **Google Sheet** — she enters/edits data
2. **Publish button** (Google Apps Script) — sends `repository_dispatch` webhook to GitHub
3. **GitHub Action** (`/.github/workflows/publish.yml`):
   - Authenticates with Google Sheets API via service account
   - Reads all tabs
   - Converts each tab to its JSON file in `data/`
   - Commits only if files changed
   - Push triggers Netlify
4. **Netlify** builds Hugo — content adapters generate pages from JSON
5. **Site live** ~2 minutes after button click

### GitHub Action trigger

- Primary: `repository_dispatch` event from sheet button
- Backup: `workflow_dispatch` for manual trigger from GitHub

### Error handling

- If the GitHub Action fails, no commit happens, site stays as-is
- Optional email notification on failure via GitHub Actions

### Google Apps Script (in the sheet)

A simple script attached to a "Publish" button that sends a POST request to the GitHub Actions API with a personal access token stored as a script property.

## Google Sheet Structure

One Google Sheet with one tab per content type. Column headers match the JSON field names. Each row is one entry.

Tabs: Publications, Projects, Books, Conferences, Talks, Contracts, Theses, Materials

## Initial Migration

### Steps

1. **Parse existing markdown** — one-time Python script extracts all entries from current Hugo content files into the JSON structure
2. **Write JSON files** to `data/`
3. **Build content adapters** — create `_content.gotmpl` files for each content type
4. **Verify** — run `hugo server` and compare output against current site. Content should be equivalent with cleaner/more consistent formatting
5. **Remove old markdown files** — delete the hand-written markdown for the 8 migrated content types
6. **Populate Google Sheet** — generate CSVs from JSON for import into Google Sheets. From this point, the sheet is the source of truth
7. **Wire up pipeline** — set up GitHub Action and Google Apps Script publish button

### Migration order

Do publications first (most complex) to validate the full pipeline end-to-end, then migrate the remaining content types.
