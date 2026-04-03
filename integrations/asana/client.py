"""
Asana REST client: list active (incomplete) tasks for named assignees, then filter by brand.

Brand keywords match task title, plain notes, HTML-stripped description, and custom field text
(see ``integrations.asana.brands.task_search_text``). Comments/stories are not fetched.

Uses GET /workspaces/{gid}/users to resolve names.

Tasks: Asana does **not** allow ``assignee`` + ``project`` on ``GET /tasks`` (400). With a
``project_gid`` we paginate top-level tasks, then walk subtasks (see ``ASANA_PROJECT_INCLUDE_SUBTASKS``).
By default the dashboard shows **subtasks only** (``ASANA_DASHBOARD_SUBTASKS_ONLY``): parent rows
from the project list are dropped after expansion. Workspace scope uses ``parent`` on each task
to apply the same filter. Without a project, we use ``assignee`` + ``workspace`` per user.
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
    "num_subtasks",
    "permalink_url",
    "assignee",
    "assignee.gid",
    "assignee.name",
    "parent",
    "parent.gid",
    # Brand keyword search also scans custom field labels and values (see brands.task_search_text).
    "custom_fields.name",
    "custom_fields.text_value",
    "custom_fields.display_value",
    "custom_fields.number_value",
    "custom_fields.enum_value",
    "custom_fields.enum_value.name",
    "custom_fields.multi_enum_values",
    "custom_fields.multi_enum_values.name",
)


class AsanaConfigError(RuntimeError):
    """Missing or invalid configuration for live Asana calls."""


@dataclass(frozen=True)
class DashboardFetchResult:
    """Live fetch outcome for the Streamlit app."""

    tasks_by_brand: dict[str, list[dict[str, Any]]]
    resolved_assignees: tuple[tuple[str, str], ...]  # (display_name, gid)
    missing_assignees: tuple[str, ...]
    tasks_in_scope: int  # open tasks for assignees after project/workspace scope, before brand filter
    sample_task_titles: tuple[str, ...]  # first few titles for troubleshooting
    scope_includes_unassigned_incomplete: bool = False  # project mode: unassigned rows included
    subtasks_only: bool = True  # dashboard rows are subtasks only (not parent tasks)


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


def _task_assignee_gid(task: dict[str, Any]) -> str | None:
    a = task.get("assignee")
    if isinstance(a, dict) and a.get("gid"):
        return str(a["gid"])
    return None


def _is_task_incomplete(task: dict[str, Any]) -> bool:
    """True when the task is not marked completed (open / incomplete only)."""
    return task.get("completed") is not True


def _task_is_subtask(task: dict[str, Any]) -> bool:
    """True when Asana reports a parent task (this row is a subtask)."""
    p = task.get("parent")
    return isinstance(p, dict) and bool(p.get("gid"))


def project_include_unassigned_from_env() -> bool:
    """
    When scoping by project, also include incomplete tasks with no assignee.

    Default is **false** (only tasks assigned to configured assignees). Set
    ``ASANA_PROJECT_INCLUDE_UNASSIGNED=true`` if your board lists tasks with
    ``assignee: null`` in the API but you still want them in the dashboard.
    """
    raw = os.environ.get("ASANA_PROJECT_INCLUDE_UNASSIGNED", "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _filter_project_tasks_for_assignees(
    raw: list[dict[str, Any]],
    allowed: set[str],
    *,
    include_unassigned: bool,
) -> list[dict[str, Any]]:
    """Keep incomplete tasks assigned to ``allowed``, and optionally unassigned ones."""
    out: list[dict[str, Any]] = []
    for t in raw:
        if not _is_task_incomplete(t):
            continue
        ag = _task_assignee_gid(t)
        if ag:
            if ag in allowed:
                out.append(t)
        elif include_unassigned:
            out.append(t)
    return out


def project_include_subtasks_from_env() -> bool:
    """
    After listing top-level project tasks, also fetch each task's subtasks (recursive).

    Default **true**. Set ``ASANA_PROJECT_INCLUDE_SUBTASKS=false`` to skip the walk (not
    compatible with :func:`dashboard_subtasks_only_from_env` when that is true — expansion
    is forced for project scope). Uses :func:`project_subtask_fetch_workers_from_env`.
    """
    raw = os.environ.get("ASANA_PROJECT_INCLUDE_SUBTASKS", "true").strip().lower()
    return raw not in ("0", "false", "no", "off")


def dashboard_subtasks_only_from_env() -> bool:
    """
    Dashboard rows are **subtasks only** (drop top-level project tasks / parents).

    Default **true**. Set ``ASANA_DASHBOARD_SUBTASKS_ONLY=false`` to show parent tasks too
    (after expansion). Workspace scope uses ``parent`` on each task; project scope drops
    rows whose gid came from the initial project list.
    """
    raw = os.environ.get("ASANA_DASHBOARD_SUBTASKS_ONLY", "true").strip().lower()
    return raw not in ("0", "false", "no", "off")


def project_should_expand_subtasks(project_gid: str | None) -> bool:
    """Expand subtasks when subtasks-only mode needs them, or when explicitly enabled."""
    if project_gid and project_gid.strip() and dashboard_subtasks_only_from_env():
        return True
    return project_include_subtasks_from_env()


def project_subtask_fetch_workers_from_env() -> int:
    """Parallelism for subtask GETs when project subtasks are enabled (default ``8``, max ``32``)."""
    raw = os.environ.get("ASANA_PROJECT_SUBTASK_MAX_CONCURRENCY", "8").strip()
    try:
        n = int(raw)
    except ValueError:
        n = 8
    return max(1, min(n, 32))


def project_subtask_max_depth_from_env() -> int:
    """How many subtask levels to walk under each project task (default ``5``)."""
    raw = os.environ.get("ASANA_PROJECT_SUBTASK_MAX_DEPTH", "").strip()
    if not raw:
        return 5
    try:
        n = int(raw)
        return max(0, min(n, 20))
    except ValueError:
        return 5


def _paginate_subtasks_for_task(
    session: requests.Session,
    parent_task_gid: str,
) -> list[dict[str, Any]]:
    """Paginate ``GET /tasks/{parent}/subtasks`` with the same fields as project tasks."""
    collected: list[dict[str, Any]] = []
    offset: str | None = None
    opt = ",".join(TASK_OPT_FIELDS)

    while True:
        params: dict[str, Any] = {
            "limit": 100,
            "opt_fields": opt,
        }
        if offset:
            params["offset"] = offset

        payload = _request_json(session, f"/tasks/{parent_task_gid}/subtasks", params)
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


def _new_session_for_token(token: str) -> requests.Session:
    s = requests.Session()
    s.headers.update(_headers(token))
    return s


def _expand_project_tasks_with_subtasks(
    tasks: list[dict[str, Any]],
    *,
    max_depth: int,
    token: str,
) -> list[dict[str, Any]]:
    """
    Merge in subtasks level-by-level. Each level parallelizes GET /tasks/{{parent}}/subtasks.

    Asana's ``GET /tasks?project=...`` omits subtasks; they only appear under
    ``GET /tasks/{parent}/subtasks``.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    by_gid: dict[str, dict[str, Any]] = {}
    for t in tasks:
        gid = t.get("gid")
        if gid:
            by_gid[str(gid)] = t

    if not by_gid:
        return []

    fetched_parents: set[str] = set()
    workers = project_subtask_fetch_workers_from_env()
    current_level: list[str] = [str(t["gid"]) for t in tasks if t.get("gid")]

    def fetch_one(pgid: str) -> tuple[str, list[dict[str, Any]]]:
        s = _new_session_for_token(token)
        return pgid, _paginate_subtasks_for_task(s, pgid)

    for _ in range(max_depth):
        pending: list[str] = []
        for pgid in current_level:
            if pgid in fetched_parents:
                continue
            pt = by_gid.get(pgid)
            if not isinstance(pt, dict):
                fetched_parents.add(pgid)
                continue
            ns = pt.get("num_subtasks")
            if ns == 0:
                fetched_parents.add(pgid)
                continue
            pending.append(pgid)

        if not pending:
            break

        next_level: list[str] = []
        with ThreadPoolExecutor(max_workers=workers) as ex:
            fut_to_pgid = {ex.submit(fetch_one, pgid): pgid for pgid in pending}
            for fut in as_completed(fut_to_pgid):
                pgid = fut_to_pgid[fut]
                try:
                    _, st_list = fut.result()
                except Exception:
                    logger.exception("Asana subtasks fetch failed for parent %s", pgid)
                    st_list = []
                fetched_parents.add(pgid)
                for st in st_list:
                    sg = st.get("gid")
                    if not sg:
                        continue
                    sgid = str(sg)
                    if sgid not in by_gid:
                        by_gid[sgid] = st
                        next_level.append(sgid)

        current_level = next_level

    return list(by_gid.values())


def _paginate_tasks_in_project(
    session: requests.Session,
    project_gid: str,
) -> list[dict[str, Any]]:
    """Paginate open tasks in a project (do not combine with assignee — API returns 400)."""
    collected: list[dict[str, Any]] = []
    offset: str | None = None
    opt = ",".join(TASK_OPT_FIELDS)

    while True:
        params: dict[str, Any] = {
            "project": project_gid,
            "completed_since": "now",
            "limit": 100,
            "opt_fields": opt,
        }
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
    include_unassigned_in_project: bool | None = None,
) -> list[dict[str, Any]]:
    """
    Incomplete (open) tasks for any of the given assignee user gids.

    With ``project_gid``: paginate tasks **in that project** only, then keep tasks assigned
    to one of ``assignee_gids`` (Asana forbids ``assignee`` + ``project`` query params).
    Unassigned tasks in the project are included when ``include_unassigned_in_project`` is
    True (default from :func:`project_include_unassigned_from_env`).

    Without ``project_gid``: paginate per assignee with ``assignee`` + ``workspace``.
    """
    session = requests.Session()
    session.headers.update(_headers(token))

    assignee_gids = list(dict.fromkeys(assignee_gids))
    allowed = set(assignee_gids)

    if project_gid and project_gid.strip():
        if include_unassigned_in_project is None:
            include_unassigned_in_project = project_include_unassigned_from_env()
        pg = project_gid.strip()
        top_level = _paginate_tasks_in_project(session, pg)
        top_gids = {str(t["gid"]) for t in top_level if t.get("gid")}
        raw: list[dict[str, Any]] = list(top_level)
        if project_should_expand_subtasks(project_gid):
            raw = _expand_project_tasks_with_subtasks(
                top_level,
                max_depth=project_subtask_max_depth_from_env(),
                token=token,
            )
        if dashboard_subtasks_only_from_env():
            raw = [t for t in raw if t.get("gid") and str(t["gid"]) not in top_gids]
        return _filter_project_tasks_for_assignees(
            raw,
            allowed,
            include_unassigned=include_unassigned_in_project,
        )

    by_task_gid: dict[str, dict[str, Any]] = {}
    for agid in assignee_gids:
        batch = _paginate_tasks_for_assignee(session, agid, workspace_gid, None)
        for t in batch:
            if not _is_task_incomplete(t):
                continue
            gid = t.get("gid")
            if gid:
                by_task_gid[str(gid)] = t
    raw_ws = list(by_task_gid.values())
    if dashboard_subtasks_only_from_env():
        raw_ws = [t for t in raw_ws if _task_is_subtask(t)]
    return raw_ws


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

    inc_unassigned = project_include_unassigned_from_env() if project_gid else False
    raw = fetch_incomplete_tasks_for_assignees(
        token,
        ws,
        gids,
        project_gid=project_gid,
        include_unassigned_in_project=inc_unassigned if project_gid else None,
    )

    gid_to_name = {str(u["gid"]): (u.get("name") or "").strip() for u in users if u.get("gid")}

    resolved_pairs: list[tuple[str, str]] = []
    for gid in gids:
        display = gid_to_name.get(gid, gid)
        resolved_pairs.append((display, gid))

    out: dict[str, list[dict[str, Any]]] = {}
    for brand in BRAND_KEYWORDS:
        out[brand] = filter_tasks_for_brand(raw, brand)

    titles = tuple(
        (t.get("name") or "").strip() for t in raw[:12] if isinstance(t, dict)
    )

    return DashboardFetchResult(
        tasks_by_brand=out,
        resolved_assignees=tuple(resolved_pairs),
        missing_assignees=tuple(missing),
        tasks_in_scope=len(raw),
        sample_task_titles=titles,
        scope_includes_unassigned_incomplete=bool(project_gid and inc_unassigned),
        subtasks_only=dashboard_subtasks_only_from_env(),
    )


def workspace_gid_from_env() -> str | None:
    gid = os.environ.get("ASANA_WORKSPACE_GID")
    return gid.strip() if gid else None


def task_scope_is_workspace() -> bool:
    """If True, fetch uses assignee+workspace (no project filter). Set ``ASANA_TASK_SCOPE=workspace``."""
    return os.environ.get("ASANA_TASK_SCOPE", "project").strip().lower() == "workspace"


def get_task_fetch_project_gid(streamlit_secret: str | None = None) -> str | None:
    """
    Project GID for scoped fetch, or None to use workspace-wide assignee queries.

    When :func:`task_scope_is_workspace` is True, returns None regardless of project default.
    """
    if task_scope_is_workspace():
        return None
    return get_project_gid(streamlit_secret)


def get_project_gid(streamlit_secret: str | None = None) -> str:
    """
    Project GID used to scope tasks (paginate by project, then filter assignees in app).

    Order: ``ASANA_PROJECT_GID`` env → optional Streamlit secret → :data:`DEFAULT_PROJECT_GID`.
    """
    raw = os.environ.get("ASANA_PROJECT_GID")
    if raw is not None and raw.strip():
        return raw.strip()
    if streamlit_secret is not None and str(streamlit_secret).strip():
        return str(streamlit_secret).strip()
    return DEFAULT_PROJECT_GID
