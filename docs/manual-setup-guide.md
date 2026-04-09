# Google Sheets CMS — Manual Setup Guide

These are the remaining steps to complete the Google Sheets CMS setup. All code and automation is already in place.

## 1. Add GitHub Secret

Go to https://github.com/DignaCouso/dignacouso-www/settings/secrets/actions and add:

- **`GOOGLE_SHEET_ID`**: The Sheet ID (you'll get this in step 2 — come back to add it after creating the sheet)

## 2. Create and Populate the Google Sheet

### Generate CSVs from current data

On your machine, run:

```bash
cd /home/javi/projects/dignacouso-www
python3 scripts/json_to_csv.py
```

This creates CSV files in `sheets_csv/`:
- publications.csv, projects.csv, books.csv, conferences.csv, talks.csv, contracts.csv, theses.csv, materials.csv

### Create the Google Sheet

1. Go to https://sheets.google.com and create a new spreadsheet
2. Name it something like "Digna Couso — Website Data"
3. Copy the **Sheet ID** from the URL — it's the long string between `/d/` and `/edit`:
   ```
   https://docs.google.com/spreadsheets/d/THIS_IS_THE_SHEET_ID/edit
   ```
4. Go back to GitHub secrets (step 1) and add this as `GOOGLE_SHEET_ID`

### Import the CSVs

For each CSV file:

1. In the Google Sheet, go to File > Import
2. Click the "Upload" tab and select the CSV file
3. Choose "Insert new sheet" as the import location
4. Click "Import data"
5. Rename the new tab to match exactly (case-sensitive):
   - `Publications`, `Projects`, `Books`, `Conferences`, `Talks`, `Contracts`, `Theses`, `Materials`
6. Delete the default empty "Sheet1" tab

### Make the sheet public

1. Click the "Share" button in the top-right of the Google Sheet
2. Under "General access", change from "Restricted" to **"Anyone with the link"**
3. Set the role to **Viewer**
4. Click "Done"

### Set up sheet protections

For each tab:

1. **Freeze the header row**: View > Freeze > 1 row
2. **Add data validation for type/enum columns** (optional but recommended):
   - Select the column with type values (e.g., column J "type" in Publications)
   - Data > Data validation > Add rule
   - Criteria: "Dropdown (from a list of items)"
   - Enter the allowed values (e.g., `indexed-jcr, indexed-other, non-indexed, conference-derived, other`)
   - Click Done
3. **Protect the header row** (optional):
   - Select row 1
   - Data > Protect sheets and ranges
   - Set permissions so only you can edit

## 3. Publishing

Publishing is automatic. A GitHub Action runs every hour on the top of the hour (see `.github/workflows/publish.yml`), fetches all sheet tabs, regenerates the JSON in `data/`, and only commits/pushes when something actually changed. Netlify redeploys the site on each push to `main`.

If you want to publish immediately without waiting for the next hourly run:

1. Go to https://github.com/DignaCouso/dignacouso-www/actions
2. Click the **"Publish from Google Sheets (hourly)"** workflow in the left sidebar
3. Click **"Run workflow"** > **"Run workflow"**

Note: scheduled GitHub Actions can be delayed by 5–15 minutes under load. This is normal.

## 4. End-to-End Test

1. In the Google Sheet, go to the "Materials" tab (simplest content type)
2. Add a test row at the bottom:
   - year: `2099`
   - authors: `Test Author`
   - title: `Test Entry — Delete Me`
   - publisher: `Test Publisher`
   - url: (leave empty)
3. Trigger the workflow manually from the Actions UI (see step 3 above), or wait for the next hourly run
4. Check the results:
   - GitHub Actions: the workflow should show a successful run
   - Live site: https://dignacouso.me/material-didactic/ — the test entry should appear
5. **Remove the test entry**: delete the row from the sheet, trigger the workflow again, verify it disappears from the site

## 5. Cleanup (if upgrading from the old Apps Script publish flow)

The previous setup used a Google Apps Script in the sheet to call the GitHub API directly. That is no longer needed:

- **Delete the Apps Script**: in the Google Sheet, Extensions > Apps Script, delete the project.
- **Revoke the old GitHub PAT**: go to https://github.com/settings/tokens and delete the fine-grained token that was used by the Apps Script.

## Troubleshooting

**GitHub Action fails:**
- Go to https://github.com/DignaCouso/dignacouso-www/actions and click the failed run
- Check the logs for error details
- Common issues: `GOOGLE_SHEET_ID` secret missing/wrong, sheet not set to public

**Site doesn't update after a successful Action run:**
- The run may have detected no changes — check the "Check for changes" step output
- Check Netlify deploys at https://app.netlify.com/ — it should auto-deploy on push
- The branch must be set as the production branch in Netlify

**Edit in the sheet hasn't appeared yet:**
- The cron runs hourly and can be delayed up to ~15 minutes. Trigger manually from the Actions UI if you need it sooner.
