"""
Verify Google Workspace domain-wide delegation: service account impersonates a user and
calls Gmail (readonly) and Calendar (readonly).

Prereqs:
  pip install -r requirements-google-workspace.txt

Credentials (pick one):
  - GOOGLE_APPLICATION_CREDENTIALS — path to the downloaded SA JSON file (local dev), OR
  - GOOGLE_SERVICE_ACCOUNT_JSON — full JSON string (e.g. from GitHub Actions secret)

  WORKSPACE_IMPERSONATE_USER — defaults to dave@twowombats.com

Loads .env from repo root if python-dotenv is installed.

Does not print email bodies; only counts and safe metadata.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

SCOPES = (
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
)


def _load_credentials():
    from google.oauth2 import service_account

    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if raw:
        info = json.loads(raw)
        return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)

    path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if path and Path(path).is_file():
        return service_account.Credentials.from_service_account_file(path, scopes=SCOPES)

    print(
        "Set GOOGLE_APPLICATION_CREDENTIALS to your SA JSON path, or "
        "GOOGLE_SERVICE_ACCOUNT_JSON to the JSON string.",
        file=sys.stderr,
    )
    sys.exit(1)


def main() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    except ImportError:
        pass

    user = os.environ.get("WORKSPACE_IMPERSONATE_USER", "dave@twowombats.com").strip()
    base = _load_credentials()
    delegated = base.with_subject(user)

    # Gmail
    from googleapiclient.discovery import build

    gmail = build("gmail", "v1", credentials=delegated, cache_discovery=False)
    gresp = gmail.users().messages().list(userId="me", maxResults=5).execute()
    messages = gresp.get("messages") or []
    print(f"Gmail OK — impersonating {user}")
    print(f"  Recent message count (up to 5): {len(messages)}")
    for i, m in enumerate(messages[:3]):
        mid = m.get("id")
        if not mid:
            continue
        meta = gmail.users().messages().get(userId="me", id=mid, format="metadata").execute()
        headers = {h["name"]: h["value"] for h in (meta.get("payload") or {}).get("headers") or []}
        subj = headers.get("Subject", "(no subject)")[:120]
        print(f"  [{i + 1}] {subj}")

    # Calendar (smoke test)
    cal = build("calendar", "v3", credentials=delegated, cache_discovery=False)
    cresp = (
        cal.events()
        .list(calendarId="primary", maxResults=3, singleEvents=True, orderBy="startTime")
        .execute()
    )
    events = cresp.get("items") or []
    print(f"Calendar OK — upcoming sample count: {len(events)}")
    for i, ev in enumerate(events[:3]):
        start = ev.get("start", {}).get("dateTime") or ev.get("start", {}).get("date", "")
        print(f"  [{i + 1}] {start} — {(ev.get('summary') or '(no title)')[:80]}")


if __name__ == "__main__":
    main()
