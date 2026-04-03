"""
Asana REST client: list active (incomplete) tasks for named assignees, then filter by brand.

Uses GET /workspaces/{gid}/users to resolve names, then GET /tasks per assignee with
workspace + completed_since=now (see Asana docs).
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any

import requests

from integrations.asana.brands import BRAND_KEYWORDS, filter_tasks_for_brand

logger = logging.getLogger(__name__)

ASANA_API_BASE = "https://app.asana.com/api/1.0"

# Default project for task queries (override with ASANA_PROJECT_GID).
DEFAULT_PROJECT_GID = "1209401086303491"

# Default dashboard assignees (override with ASANA_ASSIGNEE_NAMES=comma,separated)
DEFAULT_ASSIGNEE_NAMES: tuple[str, ...] = ("Alan Doran", "Cormac Folan")

TASK_OPT_FIELDS: tuple[str, ...] = (
    "gid",
    "name",
    "notes",
    "html_notes",
    "completed",
    "due_on",
    "permalink_url",
    "assignee",
    "assignee.name",
)


class AsanaConfigError(RuntimeError):
    """Missing or invalid configuration for live Asana calls."""


@dataclass(frozen=True)
class DashboardFetchResult:
    """Live fetch outcome for the Streamlit app."""

    tasks_by_brand: dict[str, list[dict[str, Any]]]
    resolved_assignees: tuple[tuple[str, str], ...]  # (display_name, gid)
    missing_assignees: tuple[str, ...]


def get_asana_token() -> str | None:
    """Prefer ASANA_ACCESS_TOKEN; fall back to ASANA_PAT (used elsewhere in this repo)."""
    return os.environ.get("ASANA_ACCESS_TOKEN") or os.environ.get("ASANA_PAT") or None


def assignee_names_from_env() -> list[str]:
    raw = os.environ.get("ASANA_ASSIGNEE_NAMES", "").strip()
    if raw:
        return [x.strip() for x in raw.split(",") if x.strip()]
    return list(DEFAULT_ASSIGNEE_NAMES)


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


def _norm_person_name(name: str) -> str:
    return " ".join(name.split()).lower()


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


def list_workspace_users(session: requests.Session, workspace_gid: str) -> list[dict[str, Any]]:
    payload = _request_json(
        session,
        f"/workspaces/{workspace_gid}/users",
        {"opt_fields": "name,email,gid"},
    )
    data = payload.get("data") or []
    return [x for x in data if isinstance(x, dict)]


def resolve_assignee_gids_from_user_list(
    users: list[dict[str, Any]],
    display_names: list[str],
) -> tuple[list[str], list[str]]:
    """
    Match display names (case-insensitive, whitespace-normalized) to user gids.

    Returns (gids_in_order, missing_names).
    """
    by_norm: dict[str, str] = {}
    for u in users:
        nm = (u.get("name") or "").strip()
        gid = u.get("gid")
        if nm and gid:
            by_norm[_norm_person_name(nm)] = str(gid)

    gids: list[str] = []
    missing: list[str] = []
    for name in display_names:
        n = name.strip()
        if not n:
            continue
        gid = by_norm.get(_norm_person_name(n))
        if gid:
            gids.append(gid)
        else:
            missing.append(n)
    return gids, missing


def _paginate_tasks_for_assignee(
    session: requests.Session,
    assignee_gid: str,
    workspace_gid: str,
    project_gid: str | None,
) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    offset: str | None = None
    opt = ",".join(TASK_OPT_FIELDS)

    while True:
        params: dict[str, Any] = {
            "assignee": assignee_gid,
            "completed_since": "now",
            "limit": 100,
            "opt_fields": opt,
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


def fetch_incomplete_tasks_for_assignees(
    token: str,
    workspace_gid: str,
    assignee_gids: list[str],
    *,
    project_gid: str | None = None,
) -> list[dict[str, Any]]:
    """Incomplete tasks for any of the given assignee user gids; deduped by task gid."""
    session = requests.Session()
    session.headers.update(_headers(token))

    assignee_gids = list(dict.fromkeys(assignee_gids))
    by_task_gid: dict[str, dict[str, Any]] = {}
    for agid in assignee_gids:
        batch = _paginate_tasks_for_assignee(session, agid, workspace_gid, project_gid)
        for t in batch:
            gid = t.get("gid")
            if gid:
                by_task_gid[str(gid)] = t
    return list(by_task_gid.values())


def fetch_active_tasks_for_dashboard(
    token: str | None,
    workspace_gid: str | None,
    *,
    project_gid: str | None = None,
) -> DashboardFetchResult:
    """
    Return brand → tasks for configured assignees (see DEFAULT_ASSIGNEE_NAMES / env).

    Raises AsanaConfigError if token or workspace is missing, or if no assignee gids resolve.
    """
    if not token or not workspace_gid:
        raise AsanaConfigError("ASANA_ACCESS_TOKEN/ASANA_PAT and ASANA_WORKSPACE_GID are required")

    ws = workspace_gid.strip()
    names = assignee_names_from_env()
    session = requests.Session()
    session.headers.update(_headers(token))

    users = list_workspace_users(session, ws)
    gids, missing = resolve_assignee_gids_from_user_list(users, names)
    if not gids:
        raise AsanaConfigError(
            "No assignees matched in workspace. "
            f"Looked for: {names}. Not found: {missing or names}"
        )
    if missing:
        logger.warning("Assignee names not found in workspace (skipping): %s", missing)

    raw = fetch_incomplete_tasks_for_assignees(token, ws, gids, project_gid=project_gid)

    gid_to_name = {str(u["gid"]): (u.get("name") or "").strip() for u in users if u.get("gid")}

    resolved_pairs: list[tuple[str, str]] = []
    for gid in gids:
        display = gid_to_name.get(gid, gid)
        resolved_pairs.append((display, gid))

    out: dict[str, list[dict[str, Any]]] = {}
    for brand in BRAND_KEYWORDS:
        out[brand] = filter_tasks_for_brand(raw, brand)

    return DashboardFetchResult(
        tasks_by_brand=out,
        resolved_assignees=tuple(resolved_pairs),
        missing_assignees=tuple(missing),
    )


def workspace_gid_from_env() -> str | None:
    gid = os.environ.get("ASANA_WORKSPACE_GID")
    return gid.strip() if gid else None


def get_project_gid(streamlit_secret: str | None = None) -> str:
    """
    Project GID for GET /tasks (assignee + project scope).

    Order: ``ASANA_PROJECT_GID`` env → optional Streamlit secret → :data:`DEFAULT_PROJECT_GID`.
    """
    raw = os.environ.get("ASANA_PROJECT_GID")
    if raw is not None and raw.strip():
        return raw.strip()
    if streamlit_secret is not None and str(streamlit_secret).strip():
        return str(streamlit_secret).strip()
    return DEFAULT_PROJECT_GID
