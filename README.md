# excel-to-gsheet-sync

Reads rows from local Excel files (in a folder) or from another Google Sheet, and
appends them to a destination Google Sheet — building up a running history every
time you run it.

If the source data hasn't changed since the last run, it skips the run instead of
adding duplicate rows.

## Setup

1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. In [Google Cloud Console](https://console.cloud.google.com/), create a project,
   enable the **Google Sheets API** and **Google Drive API**, then create a
   **Service Account** and download its JSON key.

3. Save that key as `credentials.json` in this folder. **Never commit this file** —
   it's already excluded via `.gitignore` because it's a secret key.

4. Open the JSON key file and copy the `client_email` value (looks like
   `something@your-project.iam.gserviceaccount.com`).

5. Share your source Google Sheet (if using one) and your destination Google Sheet
   with that email address, giving it **Editor** access.

## Usage

**From local Excel files:**
```bash
python sync_to_sheet.py --source excel --source-path "C:\path\to\folder" --dest-id YOUR_DEST_SHEET_ID --dest-tab Sheet1
```

**From another Google Sheet:**
```bash
python sync_to_sheet.py --source gsheet --source-path SOURCE_SHEET_ID --source-tab Sheet1 --dest-id YOUR_DEST_SHEET_ID --dest-tab Sheet1
```

The Sheet ID is the long string in its URL:
`docs.google.com/spreadsheets/d/<THIS PART>/edit`

### Windows shortcuts

`sync_from_excel.bat` and `sync_from_gsheet.bat` wrap the commands above with
pre-filled paths/IDs — edit them with your own folder path and Sheet IDs, then just
double-click to run.

## How duplicate-skipping works

Each run hashes the *entire* batch of source data and compares it to the hash from
the last run (stored in `sync_state.json`, which is local only and not committed).
If the source is byte-for-byte the same as last time, the run is skipped.

This fits a "replace all the data in the source each time" workflow. If you instead
add a single new row without removing old ones, the whole batch will look different
and get re-appended in full — so it works best when the source is fully replaced
between runs.
