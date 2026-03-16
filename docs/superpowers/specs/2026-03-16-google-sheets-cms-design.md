# Google Sheets CMS for Academic Website

## Summary

Replace manual Hugo markdown editing with a Google Sheets-based content management system. Dr. Digna Couso maintains her academic data (publications, projects, etc.) in a Google Sheet. A publish button triggers a GitHub Action that converts the sheet data to JSON files, which Hugo content adapters use to generate trilingual pages (ca/es/en) at build time.

## Context

- **Site:** dignacouso.me — trilingual (ca/es/en) academic portfolio built with Hugo + Hyde theme, deployed on Netlify
- **Problem:** The site owner is not comfortable editing Hugo markdown files directly
- **Constraint:** She works from one Windows computer with no technical tools installed (no Git, Python, etc.). She needs full autonomy — no technical help required to publish
- **Content update pattern:** All data available at once when adding entries; updates all content types

## Prerequisites

### Hugo version upgrade

Content adapters require Hugo >= 0.126.0. The current installed version is 0.123.7. Must upgrade both locally and on Netlify.

### Netlify configuration

Create `netlify.toml` to pin the Hugo version and build settings:

```toml
[build]
  command = "hugo"
  publish = "public"

[build.environment]
  HUGO_VERSION = "0.145.0"
```

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

All data is language-independent. Translations of section headings and field labels are handled in Hugo content adapter templates. Entries are stored sorted by year descending in the JSON files.

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

### Language directory compatibility

The site uses per-language `contentDir` configuration (`content/ca/`, `content/en/`, `content/es/`). Content adapters must be placed inside each language directory. Each adapter is identical — it detects its language from `.Site.Language.Lang` and renders accordingly.

### URL preservation

Adapter directories use the current Catalan slug names as directory names. English and Spanish `_index.md` files include a `slug` field to preserve the current translated URLs.

| Content Type | Directory Name | ES slug | EN slug |
|---|---|---|---|
| Publications | `publicacions-cientifiques/` | `publicaciones-cientificas` | `scientific-publications` |
| Research Projects | `projectes-de-recerca/` | `proyectos-de-investigacion` | `research-projects` |
| Books and Chapters | `llibres-i-capitols/` | `libros-y-capitulos` | `books-and-chapters` |
| Conference Contributions | `aportacions-a-congressos/` | `aportaciones-a-congresos` | `conference-contributions` |
| Invited Talks | `conferencies/` | `conferencias` | `conferences` |
| Contracts and Agreements | `contractes-i-convenis/` | `contratos-y-convenios` | `contracts-and-agreements` |
| Thesis Supervision | `direccio-de-treballs/` | `direccion-de-trabajos` | `doctoral-thesis-supervision` |
| Teaching Materials | `material-didactic/` | `material-didactico` | `teaching-materials` |

### File structure

Each content type has a `_content.gotmpl` in each language directory. No `_index.md` files are needed — the adapter generates the full section page via `.AddPage` with `kind: "section"`, including title, slug, menu, and body content. The adapters are identical copies — they detect the active language at build time.

```
content/
├── ca/
│   ├── publicacions-cientifiques/
│   │   └── _content.gotmpl
│   ├── projectes-de-recerca/
│   │   └── _content.gotmpl
│   ├── ... (other content types, same pattern)
│   ├── ressenya-biografica.md  (static, manually edited)
│   ├── formacio.md             (static)
│   └── reconeixements.md       (static)
├── en/
│   ├── publicacions-cientifiques/
│   │   └── _content.gotmpl
│   ├── projectes-de-recerca/
│   │   └── _content.gotmpl
│   └── ... (same structure)
├── es/
│   ├── publicacions-cientifiques/
│   │   └── _content.gotmpl
│   ├── projectes-de-recerca/
│   │   └── _content.gotmpl
│   └── ... (same structure)
data/
├── publications.json
├── projects.json
├── books.json
├── conferences.json
├── talks.json
├── contracts.json
├── theses.json
└── materials.json
```

### Menu weights

The adapter sets the menu weight for each content type to match the current site:

| Weight | Content Type | Managed by |
|---|---|---|
| 1 | Biography | static (manual) |
| 2 | Research Projects | adapter |
| 3 | Contracts and Agreements | adapter |
| 4 | Publications | adapter |
| 5 | Books and Chapters | adapter |
| 6 | Conference Contributions | adapter |
| 7 | Training/Education | static (manual) |
| 8 | Teaching Materials | adapter |
| 9 | Thesis Supervision | adapter |
| 10 | Acknowledgments | static (manual) |
| 11 | Invited Talks | adapter |

### Adapter pattern

Each adapter generates a full section page (no `_index.md` needed) by calling `.AddPage` with `kind: "section"`. This includes title, slug, menu configuration, and the rendered body content.

Each adapter follows this structure:

1. Read data from `.Site.Data` (the JSON files in `data/`)
2. Detect language from `.Site.Language.Lang`
3. Look up the translated title, slug, section headings, and field labels from translation dicts
4. Group entries by type/section
5. Generate markdown content string with proper formatting
6. Call `.AddPage` with `kind: "section"`, `title`, `path`, `params` (including `slug` and `menu`), and `content`

Example `.AddPage` call:

```go-html-template
{{ $page := dict
  "content" (dict "mediaType" "text/markdown" "value" $content)
  "kind" "section"
  "path" "publicacions-cientifiques"
  "title" (index $titles $lang)
  "params" (dict
    "slug" (index $slugs $lang)
    "menu" (dict "main" (dict "weight" 4))
  )
}}
{{ $.AddPage $page }}
```

### Translation approach

All translations are defined in the adapter templates as Go template dicts. Example:

```go-html-template
{{ $lang := .Site.Language.Lang }}

{{ $headings := dict
  "indexed-jcr" (dict
    "ca" "Articles en revistes indexades (JCR, SJR, SCOPUS)"
    "es" "Articulos en revistas indexadas (JCR, SJR, SCOPUS)"
    "en" "Publications on journals with impact factor (JCR, SJR, SCOPUS)"
  )
}}

{{ $labels := dict
  "funding" (dict "ca" "Entitat Finançadora" "es" "Entidad Financiadora" "en" "Funding Entity")
  "duration" (dict "ca" "Durada" "es" "Duración" "en" "Duration")
  "pi" (dict "ca" "IP" "es" "IP" "en" "PI")
}}
```

Field labels (e.g., "Funding Entity" / "Entitat Finançadora" / "Entidad Financiadora") follow the same pattern.

### Zotero RIS link

The existing Zotero RIS download link on the publications page and homepage is preserved. The publications adapter includes it as a static link in the generated content. The RIS file generation script (`scripts/generate_ris.py`) is updated to read from `data/publications.json` instead of parsing markdown.

## Publish Pipeline

### Flow

1. **Google Sheet** — she enters/edits data
2. **Publish button** (Google Apps Script) — sends `repository_dispatch` webhook to GitHub
3. **GitHub Action** (`/.github/workflows/publish.yml`):
   - Authenticates with Google Sheets API via service account
   - Reads all tabs
   - Validates data (required fields present, valid types, no empty rows)
   - Converts each tab to its JSON file in `data/`
   - Runs `hugo build` to verify the site builds successfully
   - Commits only if files changed and build succeeds
   - Push triggers Netlify
4. **Netlify** builds Hugo — content adapters generate pages from JSON
5. **Site live** ~2 minutes after button click

### GitHub Action trigger

- Primary: `repository_dispatch` event from sheet button
- Backup: `workflow_dispatch` for manual trigger from GitHub

### Data validation

Before committing, the GitHub Action validates:
- Required fields are present (e.g., year, authors, title for publications)
- Type/section values match allowed enums
- Empty rows and whitespace-only cells are stripped
- JSON is well-formed

If validation fails, the action exits with an error and no commit is made.

### Error handling

- If the GitHub Action fails (API error, validation error, build failure), no commit happens, site stays as-is
- GitHub Actions sends email notification on failure (enabled by default for repo owners)

### Google Sheets API authentication

- Create a Google Cloud project with Sheets API enabled
- Create a service account and download its JSON key
- Share the Google Sheet with the service account email (read-only access)
- Store the service account JSON key as a GitHub Actions secret (`GOOGLE_SHEETS_KEY`)
- Store the Sheet ID as a secret (`GOOGLE_SHEET_ID`)

### Google Apps Script (in the sheet)

A simple script attached to a "Publish" button that sends a POST request to the GitHub Actions API. The GitHub personal access token is stored as a Google Apps Script property (not visible in the sheet).

```javascript
function publish() {
  var token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  UrlFetchApp.fetch('https://api.github.com/repos/OWNER/REPO/dispatches', {
    method: 'post',
    headers: { 'Authorization': 'token ' + token, 'Accept': 'application/vnd.github.v3+json' },
    payload: JSON.stringify({ event_type: 'publish' })
  });
  SpreadsheetApp.getUi().alert('Publishing! The site will update in ~2 minutes.');
}
```

## Google Sheet Structure

One Google Sheet with one tab per content type. Column headers match the JSON field names. Each row is one entry.

Tabs: Publications, Projects, Books, Conferences, Talks, Contracts, Theses, Materials

The sheet is pre-populated during migration with all existing data. Column headers include a frozen header row with field names and optional helper text (via cell notes) explaining what each column expects.

### Defensive measures

- Header row is frozen and protected (cannot be accidentally deleted)
- Columns are in a fixed order; the conversion script reads by column name, not position
- Data validation rules on type/section columns (dropdown lists of allowed values)
- Conditional formatting to highlight rows with missing required fields

## Initial Migration

### Steps

1. **Upgrade Hugo** — upgrade to >= 0.126.0 locally; create `netlify.toml` pinning the version for production
2. **Parse existing markdown** — one-time Python script extracts all entries from current Hugo content files into the JSON structure
3. **Write JSON files** to `data/`
4. **Build content adapters** — create `_content.gotmpl` and `_index.md` files for each content type in each language directory
5. **Verify** — run `hugo server` and compare output against current site. Content should be equivalent with cleaner/more consistent formatting
6. **Remove old markdown files** — delete the hand-written markdown for the 8 migrated content types
7. **Populate Google Sheet** — generate CSVs from JSON for import into Google Sheets. From this point, the sheet is the source of truth
8. **Wire up pipeline** — set up Google Cloud service account, GitHub Action, GitHub secrets, and Google Apps Script publish button
9. **Update RIS script** — modify `scripts/generate_ris.py` to read from `data/publications.json`

### Migration order

Do publications first (most complex) to validate the full pipeline end-to-end, then migrate the remaining content types.
