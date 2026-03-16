# Google Sheets CMS — Manual Setup Guide

These are the remaining steps to complete the Google Sheets CMS setup. All code and automation is already in place on the `feature/google-sheets-cms` branch.

## 1. Create a Google Cloud Service Account

1. Go to https://console.cloud.google.com/
2. Create a new project (e.g., "dignacouso-cms") or use an existing one
3. Enable the **Google Sheets API**:
   - Go to APIs & Services > Library
   - Search for "Google Sheets API"
   - Click Enable
4. Create a service account:
   - Go to APIs & Services > Credentials
   - Click "Create Credentials" > "Service Account"
   - Name it something like "sheets-reader"
   - No need to grant any roles, just click through
5. Create a key for the service account:
   - Click on the service account you just created
   - Go to the "Keys" tab
   - Click "Add Key" > "Create new key" > JSON
   - Download the JSON file — you'll need its contents later
6. Copy the service account email (looks like `sheets-reader@project-name.iam.gserviceaccount.com`) — you'll need it in step 3

## 2. Add GitHub Secrets

Go to https://github.com/DignaCouso/dignacouso-www/settings/secrets/actions and add:

- **`GOOGLE_SHEETS_KEY`**: Paste the entire contents of the service account JSON key file you downloaded in step 1
- **`GOOGLE_SHEET_ID`**: The Sheet ID (you'll get this in step 3 — come back to add it after creating the sheet)

## 3. Create and Populate the Google Sheet

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
4. Go back to GitHub secrets (step 2) and add this as `GOOGLE_SHEET_ID`

### Import the CSVs

For each CSV file:

1. In the Google Sheet, go to File > Import
2. Click the "Upload" tab and select the CSV file
3. Choose "Insert new sheet" as the import location
4. Click "Import data"
5. Rename the new tab to match exactly (case-sensitive):
   - `Publications`, `Projects`, `Books`, `Conferences`, `Talks`, `Contracts`, `Theses`, `Materials`
6. Delete the default empty "Sheet1" tab

### Share with the service account

1. Click the "Share" button in the top-right of the Google Sheet
2. Add the service account email from step 1 (e.g., `sheets-reader@project-name.iam.gserviceaccount.com`)
3. Set permission to **Viewer** (read-only is sufficient)
4. Uncheck "Notify people" and click Share

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

## 4. Create a GitHub Personal Access Token

1. Go to https://github.com/settings/tokens?type=beta (fine-grained tokens)
2. Click "Generate new token"
3. Name it "Sheets Publish Button"
4. Set expiration (e.g., 1 year — you'll need to regenerate when it expires)
5. Under "Repository access", select "Only select repositories" and choose `DignaCouso/dignacouso-www`
6. Under "Permissions" > "Repository permissions", set:
   - **Contents**: Read and write
7. Click "Generate token"
8. Copy the token — you'll need it in the next step

## 5. Add the Publish Button (Google Apps Script)

1. In the Google Sheet, go to Extensions > Apps Script
2. Delete any existing code in the editor
3. Paste this code:

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

4. Click the save icon (or Ctrl+S)
5. Name the project "Publish to Website"
6. Store the GitHub token:
   - In the Apps Script editor, click the gear icon (Project Settings) on the left
   - Scroll down to "Script Properties"
   - Click "Add script property"
   - Property: `GITHUB_TOKEN`
   - Value: paste the personal access token from step 4
   - Click Save
7. Go back to the Google Sheet and reload the page
8. After reloading, a **"Website"** menu should appear in the menu bar

## 6. End-to-End Test

1. In the Google Sheet, go to the "Materials" tab (simplest content type)
2. Add a test row at the bottom:
   - year: `2099`
   - authors: `Test Author`
   - title: `Test Entry — Delete Me`
   - publisher: `Test Publisher`
   - url: (leave empty)
3. Click **Website > Publish** in the menu bar
4. You may need to authorize the script the first time (click through the Google permissions)
5. Wait ~2 minutes
6. Check the results:
   - GitHub Actions: go to https://github.com/DignaCouso/dignacouso-www/actions — the workflow should show a successful run
   - Live site: go to https://dignacouso.me/material-didactic/ — the test entry should appear
7. **Remove the test entry**: delete the row from the sheet, click Publish again, verify it disappears from the site

## Troubleshooting

**"Website" menu doesn't appear:**
- Reload the Google Sheet page
- Make sure the Apps Script was saved without errors

**Publish button shows an error:**
- Check that the GitHub token is stored correctly in Script Properties
- Check that the token has "Contents: Read and write" permission on the repo
- Check that the token hasn't expired

**GitHub Action fails:**
- Go to https://github.com/DignaCouso/dignacouso-www/actions and click the failed run
- Check the logs for error details
- Common issues: GOOGLE_SHEETS_KEY or GOOGLE_SHEET_ID secrets missing/wrong, sheet not shared with service account

**Site doesn't update after successful Action:**
- Check Netlify deploys at https://app.netlify.com/ — it should auto-deploy on push
- The branch must be set as the production branch in Netlify
