"""
Asana REST client: list active (incomplete) tasks, then filter by brand keywords.

Uses GET /tasks with assignee=me + workspace + completed_since=now (see Asana docs).
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import requests

from integrations.asana.brands import BRAND_KEYWORDS, filter_tasks_for_brand

logger = logging.getLogger(__name__)

ASANA_API_BASE = "https://app.asana.com/api/1.0"


class AsanaConfigError(RuntimeError):
    """Missing or invalid configuration for live Asana calls."""


def get_asana_token() -> str | None:
    """Prefer ASANA_ACCESS_TOKEN; fall back to ASANA_PAT (used elsewhere in this repo)."""
    return os.environ.get("ASANA_ACCESS_TOKEN") or os.environ.get("ASANA_PAT") or None


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


def _request_json(
    session: requests.Session,
    path: str,
    params: dict[str, Any],
    *,
    max_retries: int = 5,
) -> dict[str, Any]:
    url = f"{ASANA_API_BASE}{path}"
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        resp = session.get(url, params=params, timeout=60)
        if resp.status_code == 429:
            retry_after = float(resp.headers.get("Retry-After", "2"))
            logger.warning("Asana rate limited; sleeping %.1fs", retry_after)
            time.sleep(retry_after)
            continue
        if resp.status_code in (500, 502, 503, 504):
            wait = min(2**attempt, 30)
            logger.warning("Asana %s; retry in %ss", resp.status_code, wait)
            time.sleep(wait)
            last_exc = requests.HTTPError(f"{resp.status_code}: {resp.text[:500]}")
            continue
        resp.raise_for_status()
        return resp.json()
    if last_exc:
        raise last_exc
    raise RuntimeError("Asana request failed after retries")


def fetch_incomplete_tasks_assigned_to_me(
    token: str,
    workspace_gid: str,
    *,
    project_gid: str | None = None,
) -> list[dict[str, Any]]:
    """
    Paginate GET /tasks for incomplete tasks assigned to the token's user.

    ``completed_since=now`` follows Asana's pattern for "open" tasks for this query.
    """
    session = requests.Session()
    session.headers.update(_headers(token))

    collected: list[dict[str, Any]] = []
    offset: str | None = None

    while True:
        params: dict[str, Any] = {
            "assignee": "me",
            "completed_since": "now",
            "limit": 100,
            "opt_fields": ",".join(
                [
                    "gid",
                    "name",
                    "notes",
                    "html_notes",
                    "completed",
                    "due_on",
                    "permalink_url",
                ]
            ),
        }
        if project_gid:
            params["project"] = project_gid
        else:
            params["workspace"] = workspace_gid
        if offset:
            params["offset"] = offset

        payload = _request_json(session, "/tasks", params)
        batch = payload.get("data") or []
        for item in batch:
            if isinstance(item, dict):
                collected.append(item)

        next_page = payload.get("next_page")
        if isinstance(next_page, dict) and next_page.get("offset"):
            offset = str(next_page["offset"])
        else:
            break

    return collected


def fetch_active_tasks_for_dashboard(
    token: str | None,
    workspace_gid: str | None,
    *,
    project_gid: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """
    Return {brand_name: [task dicts]} for all configured brands.

    If ``token`` or ``workspace_gid`` is missing, returns an empty mapping
    (caller should use mock data).
    """
    if not token or not workspace_gid:
        raise AsanaConfigError("ASANA_ACCESS_TOKEN/ASANA_PAT and ASANA_WORKSPACE_GID are required")

    raw = fetch_incomplete_tasks_assigned_to_me(
        token, workspace_gid.strip(), project_gid=project_gid
    )
    out: dict[str, list[dict[str, Any]]] = {}
    for brand in BRAND_KEYWORDS:
        out[brand] = filter_tasks_for_brand(raw, brand)
    return out


def workspace_gid_from_env() -> str | None:
    gid = os.environ.get("ASANA_WORKSPACE_GID")
    return gid.strip() if gid else None


def project_gid_from_env() -> str | None:
    gid = os.environ.get("ASANA_PROJECT_GID")
    return gid.strip() if gid else None
