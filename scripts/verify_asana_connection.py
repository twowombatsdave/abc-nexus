#!/usr/bin/env python3
"""
Verify Asana credentials from repo-root .env (or existing environment).

Does not print tokens. Exit codes: 0 OK, 1 API error, 2 missing config.

Run from repo root:
  python scripts/verify_asana_connection.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from integrations.asana.client import get_project_gid  # noqa: E402


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(REPO_ROOT / ".env")
    except ImportError:
        pass


def main() -> int:
    _load_dotenv()
    token = os.environ.get("ASANA_ACCESS_TOKEN") or os.environ.get("ASANA_PAT")
    ws = os.environ.get("ASANA_WORKSPACE_GID", "").strip()

    if not token or not ws:
        print(
            "Missing ASANA_ACCESS_TOKEN (or ASANA_PAT) and/or ASANA_WORKSPACE_GID.\n"
            f"Copy {REPO_ROOT / '.env.example'} to {REPO_ROOT / '.env'} and fill values."
        )
        return 2

    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    r = requests.get(
        "https://app.asana.com/api/1.0/users/me",
        headers=headers,
        timeout=30,
    )
    if r.status_code != 200:
        print("GET /users/me failed:", r.status_code, r.text[:400])
        return 1
    me = r.json().get("data") or {}
    print("OK — authenticated as:", me.get("name", "?"), f"({me.get('email', 'no email')})")

    proj = get_project_gid()
    r2 = requests.get(
        "https://app.asana.com/api/1.0/tasks",
        headers=headers,
        params={
            "assignee": "me",
            "project": proj,
            "completed_since": "now",
            "limit": 5,
            "opt_fields": "name,completed",
        },
        timeout=30,
    )
    if r2.status_code != 200:
        print("GET /tasks (project sample) failed:", r2.status_code, r2.text[:400])
        return 1
    n = len(r2.json().get("data") or [])
    print("OK — sample incomplete tasks in project", proj, ":", n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
