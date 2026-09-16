"""
Read data from local Excel files (a folder) and/or a source Google Sheet,
then append it to a destination Google Sheet.

Setup (one-time):
  1. pip install -r requirements.txt
  2. Create a Google Cloud service account, enable the "Google Sheets API"
     and "Google Drive API" for its project, and download its JSON key.
     Save that file as credentials.json next to this script (or pass --credentials).
  3. Share BOTH the source Google Sheet (if used) and the destination Google
     Sheet with the service account's email (found inside credentials.json,
     field "client_email") as an Editor.
  See the README section at the bottom of this file for the full walkthrough.

Usage examples:
  # Append every Excel file in a folder to a destination sheet
  python sync_to_sheet.py --source excel --source-path "C:\\Users\\kanth\\Documents\\reports" ^
      --dest-id 1AbCDeFGhIjkLMNoPQRstuVWxyz0123456789 --dest-tab Sheet1

  # Append data from another Google Sheet to a destination sheet
  python sync_to_sheet.py --source gsheet --source-path 1SourceSheetIdHere ^
      --source-tab Sheet1 --dest-id 1DestSheetIdHere --dest-tab Sheet1
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

STATE_FILE = Path(__file__).parent / "sync_state.json"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

EXCEL_EXTENSIONS = (".xlsx", ".xlsm", ".xls")


def get_client(credentials_path: str) -> gspread.Client:
    creds_file = Path(credentials_path)
    if not creds_file.exists():
        sys.exit(
            f"Credentials file not found: {creds_file}\n"
            "Create a Google service account key and save it there, or pass --credentials."
        )
    creds = Credentials.from_service_account_file(str(creds_file), scopes=SCOPES)
    return gspread.authorize(creds)


def load_excel_folder(folder: str, pattern: str) -> pd.DataFrame:
    folder_path = Path(folder)
    if not folder_path.is_dir():
        sys.exit(f"Source folder not found: {folder_path}")

    files = sorted(p for p in folder_path.glob(pattern) if p.suffix.lower() in EXCEL_EXTENSIONS)
    if not files:
        sys.exit(f"No Excel files matching '{pattern}' found in {folder_path}")

    frames = []
    for file_path in files:
        sheets = pd.read_excel(file_path, sheet_name=None)  # dict of {sheet_name: DataFrame}
        for sheet_name, df in sheets.items():
            if df.empty:
                continue
            df = df.copy()
            df["__source_file"] = file_path.name
            df["__source_sheet"] = sheet_name
            frames.append(df)
        print(f"Read {sum(len(df) for df in sheets.values())} rows from {file_path.name}")

    return pd.concat(frames, ignore_index=True, sort=False)


def load_gsheet(client: gspread.Client, sheet_id: str, tab_name: str) -> pd.DataFrame:
    sh = client.open_by_key(sheet_id)
    ws = sh.worksheet(tab_name) if tab_name else sh.sheet1
    records = ws.get_all_records()
    if not records:
        sys.exit(f"No data found in source sheet tab '{ws.title}'")
    print(f"Read {len(records)} rows from Google Sheet tab '{ws.title}'")
    return pd.DataFrame(records)


def hash_dataframe(df: pd.DataFrame) -> str:
    payload = df.astype(str).to_csv(index=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def append_to_destination(client: gspread.Client, dest_id: str, dest_tab: str, df: pd.DataFrame) -> None:
    sh = client.open_by_key(dest_id)
    try:
        ws = sh.worksheet(dest_tab)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=dest_tab, rows=1, cols=max(len(df.columns), 1))

    existing_header = ws.row_values(1)
    df = df.fillna("")

    if not existing_header:
        # Empty sheet: write the header first.
        ws.append_row(list(df.columns), value_input_option="USER_ENTERED")
        existing_header = list(df.columns)

    # Align columns to the destination sheet's existing header where possible;
    # any new columns from the source get appended after it.
    ordered_cols = [c for c in existing_header if c in df.columns]
    extra_cols = [c for c in df.columns if c not in existing_header]
    final_cols = ordered_cols + extra_cols
    df = df[final_cols]

    if extra_cols:
        ws.update(range_name="A1", values=[existing_header + extra_cols])

    rows = df.astype(str).values.tolist()
    ws.append_rows(rows, value_input_option="USER_ENTERED")
    print(f"Appended {len(rows)} rows to '{sh.title}' -> tab '{ws.title}'")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", choices=["excel", "gsheet"], required=True, help="Where to read data from")
    parser.add_argument("--source-path", required=True, help="Local folder path (excel) or Sheet ID (gsheet)")
    parser.add_argument("--source-tab", default="", help="Source tab name (gsheet only; default: first tab)")
    parser.add_argument("--pattern", default="*.xlsx", help="Filename glob for excel source (default: *.xlsx)")
    parser.add_argument("--dest-id", required=True, help="Destination Google Sheet ID")
    parser.add_argument("--dest-tab", default="Sheet1", help="Destination tab name (default: Sheet1)")
    parser.add_argument("--credentials", default="credentials.json", help="Path to service account JSON key")
    args = parser.parse_args()

    client = get_client(args.credentials)

    if args.source == "excel":
        df = load_excel_folder(args.source_path, args.pattern)
    else:
        df = load_gsheet(client, args.source_path, args.source_tab)

    source_key = f"{args.source}:{args.source_path}:{args.source_tab}:{args.dest_id}:{args.dest_tab}"
    state = load_state()
    current_hash = hash_dataframe(df)

    if state.get(source_key) == current_hash:
        print("Source data hasn't changed since the last run — skipping to avoid duplicate rows.")
        return

    append_to_destination(client, args.dest_id, args.dest_tab, df)
    state[source_key] = current_hash
    save_state(state)


if __name__ == "__main__":
    main()
