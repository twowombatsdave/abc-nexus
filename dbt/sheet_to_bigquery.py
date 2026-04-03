import argparse
import json
import os
from typing import List, Dict

import pandas as pd
from google.cloud import bigquery
import gspread
from google.oauth2.service_account import Credentials


def infer_bq_schema(df: pd.DataFrame) -> List[bigquery.SchemaField]:
    schema: List[bigquery.SchemaField] = []
    for col in df.columns:
        series = df[col]
        dtype = "STRING"
        if pd.api.types.is_integer_dtype(series.dropna()):
            dtype = "INTEGER"
        elif pd.api.types.is_float_dtype(series.dropna()):
            dtype = "FLOAT"
        elif pd.api.types.is_bool_dtype(series.dropna()):
            dtype = "BOOLEAN"
        schema.append(bigquery.SchemaField(col, dtype, mode="NULLABLE"))
    return schema


def read_sheet(sheet_id: str, worksheet: str) -> pd.DataFrame:
    scopes = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]

    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if creds_path and os.path.exists(creds_path):
        creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
    else:
        # Support inline JSON in env (e.g., Actions secret)
        creds_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
        if not creds_json:
            raise RuntimeError(
                "Google credentials not found. Set GOOGLE_APPLICATION_CREDENTIALS to a file path or GOOGLE_APPLICATION_CREDENTIALS_JSON."
            )
        creds_dict: Dict = json.loads(creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)

    client = gspread.authorize(creds)
    ws = client.open_by_key(sheet_id).worksheet(worksheet)
    return pd.DataFrame(ws.get_all_records())


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed a BigQuery table from a Google Sheet")
    parser.add_argument("--sheet-id", required=True, help="Google Sheet ID")
    parser.add_argument("--worksheet", required=True, help="Worksheet/tab name")
    parser.add_argument("--table-id", required=True, help="BigQuery destination table: project.dataset.table")
    parser.add_argument(
        "--write-disposition",
        default="truncate",
        choices=["truncate", "append", "empty"],
        help="Write mode: truncate=WRITE_TRUNCATE, append=WRITE_APPEND, empty=WRITE_EMPTY",
    )
    parser.add_argument(
        "--required-columns",
        default="",
        help="Comma-separated list of required columns to validate (optional)",
    )

    args = parser.parse_args()

    df = read_sheet(args.sheet_id, args.worksheet)
    if df.empty:
        print("No data returned from sheet; exiting")
        return

    if args.required_columns:
        required = [c.strip() for c in args.required_columns.split(",") if c.strip()]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise RuntimeError(f"Missing required columns: {missing}. Present: {list(df.columns)}")

    # Convert obvious numeric/boolean types
    for col in df.columns:
        # try int, then float, then bool best-effort
        try:
            df[col] = pd.to_numeric(df[col], errors="raise").astype("Int64")
            continue
        except Exception:
            pass
        try:
            df[col] = pd.to_numeric(df[col], errors="raise").astype(float)
            continue
        except Exception:
            pass
        # Booleans often as 'true'/'false'
        if df[col].dropna().astype(str).str.lower().isin(["true", "false"]).all():
            df[col] = df[col].astype(str).str.lower().map({"true": True, "false": False})

    client = bigquery.Client()

    write_map = {
        "truncate": bigquery.WriteDisposition.WRITE_TRUNCATE,
        "append": bigquery.WriteDisposition.WRITE_APPEND,
        "empty": bigquery.WriteDisposition.WRITE_EMPTY,
    }
    job_config = bigquery.LoadJobConfig(
        write_disposition=write_map[args.write_disposition],
        schema=infer_bq_schema(df),
    )

    job = client.load_table_from_dataframe(df, args.table_id, job_config=job_config)
    job.result()

    print(f"Seeded {len(df)} rows to {args.table_id} with mode {args.write_disposition}")


if __name__ == "__main__":
    main()


