"""
ABC dashboard — Asana outstanding tasks by brand (ZYN, Velo, Nordic Spirit, FUMi, Killa, SYX, ELF, Clew, FEDRS, LUMi, Ubbs).

Environment (or Streamlit Cloud secrets with the same names):
  ASANA_ACCESS_TOKEN or ASANA_PAT — Personal Access Token
  ASANA_WORKSPACE_GID — workspace GID (required for live data)
  ASANA_PROJECT_GID — optional; defaults to project 1209401086303491
  ASANA_TASK_SCOPE — optional; set to `workspace` to ignore project and use workspace+assignee
  ASANA_PROJECT_INCLUDE_UNASSIGNED — optional; set true to include open tasks with no assignee in project scope
    (default is assigned-to-configured-users only).
  ASANA_PROJECT_INCLUDE_SUBTASKS — optional; set true to walk subtasks in project scope (extra API calls; default off).
  ASANA_PROJECT_SUBTASK_MAX_DEPTH — optional; max nesting depth when walking subtasks (default 5).
  ASANA_PROJECT_SUBTASK_MAX_CONCURRENCY — optional; parallel subtask GETs when subtasks enabled (default 8).
  ASANA_ASSIGNEE_NAMES — optional; comma-separated (default: Alan Doran, Cormac Folan)

Local dev: copy .env.example to .env in this folder (never commit .env),
  or run: powershell -ExecutionPolicy Bypass -File scripts/init_local_env.ps1
  Then verify: python scripts/verify_asana_connection.py

Run: python -m streamlit run hello_world.py

UI events append to logs/ui_events.txt (see integrations/ui_logging.py).
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from integrations.asana.brands import BRAND_KEYWORDS
from integrations.asana.client import (
    AsanaConfigError,
    DEFAULT_PROJECT_GID,
    assignee_names_from_env,
    fetch_active_tasks_for_dashboard,
    get_asana_token,
    get_project_gid,
    get_task_fetch_project_gid,
    task_scope_is_workspace,
    workspace_gid_from_env,
)
from integrations.asana.mock_tasks import mock_tasks_by_brand
from integrations.ui_logging import log_ui_event


def _load_dotenv_if_present() -> None:
    """Load repo-root .env so ASANA_* are visible to os.environ before Streamlit runs."""
    try:
        from dotenv import load_dotenv

        load_dotenv(Path(__file__).resolve().parent / ".env")
    except ImportError:
        pass


_load_dotenv_if_present()
st.set_page_config(page_title="ABC System — Asana", layout="wide")


def _secret(key: str) -> str | None:
    try:
        val = st.secrets[key]
        return str(val).strip() if val else None
    except Exception:
        return None


def resolve_token() -> str | None:
    return get_asana_token() or _secret("ASANA_ACCESS_TOKEN") or _secret("ASANA_PAT")


def resolve_workspace() -> str | None:
    return workspace_gid_from_env() or _secret("ASANA_WORKSPACE_GID")


def _session_id() -> str:
    if "ui_session_id" not in st.session_state:
        st.session_state.ui_session_id = str(uuid.uuid4())
    return str(st.session_state.ui_session_id)


def _log_session_start_once() -> None:
    if st.session_state.get("ui_session_started_logged"):
        return
    log_ui_event(_session_id(), "session_started", app="hello_world")
    st.session_state.ui_session_started_logged = True


def _on_brand_change() -> None:
    log_ui_event(
        _session_id(),
        "brand_selected",
        brand=st.session_state.get("brand_nav"),
    )


def _assignee_display(task: dict[str, Any]) -> str:
    a = task.get("assignee")
    if isinstance(a, dict):
        return (a.get("name") or "").strip()
    return ""


def tasks_to_dataframe(tasks: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for t in tasks:
        rows.append(
            {
                "Task": t.get("name") or "",
                "Assignee": _assignee_display(t),
                "Due": t.get("due_on") or "",
                "Link": t.get("permalink_url") or "",
            }
        )
    return pd.DataFrame(rows)


def render_brand_content(
    brand: str,
    tasks: list[dict[str, Any]],
    *,
    tasks_in_scope: int,
) -> None:
    if tasks:
        df = tasks_to_dataframe(tasks)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Link": st.column_config.LinkColumn("Open in Asana", display_text="Open"),
            },
        )
        return
    if tasks_in_scope == 0:
        st.warning(
            "No **incomplete** tasks **assigned** to your configured people in **current scope**. "
            "Add **`ASANA_TASK_SCOPE=workspace`** to `.env` (then refresh) to list their tasks across "
            "the workspace, or set **`ASANA_PROJECT_INCLUDE_UNASSIGNED=true`** if you also need "
            "unassigned rows in the project."
        )
        return
    st.info(
        f"No tasks matched **{brand}** keywords in title, notes, description, or custom fields. "
        f"**{tasks_in_scope}** task(s) in scope appear in other brand tabs or need "
        f"new keywords in `integrations/asana/brands.py`."
    )


def main() -> None:
    _log_session_start_once()
    sid = _session_id()

    with st.sidebar:
        st.title("ABC System")
        st.caption("Open (incomplete) Asana tasks by brand keyword — completed tasks are excluded.")
        st.caption(
            "Assignees: **"
            + "**, **".join(assignee_names_from_env())
            + "** (override with `ASANA_ASSIGNEE_NAMES`)."
        )
        if task_scope_is_workspace():
            st.caption(
                "Scope: **workspace** (tasks for assignees across workspace; no project filter). "
                "Unset `ASANA_TASK_SCOPE` to use the project below."
            )
        else:
            st.caption(
                f"Project: **{get_project_gid(_secret('ASANA_PROJECT_GID'))}** "
                f"(override with `ASANA_PROJECT_GID`; default `{DEFAULT_PROJECT_GID}`). "
                "Only tasks **assigned** to the people above count unless you set "
                "**`ASANA_PROJECT_INCLUDE_UNASSIGNED=true`**. "
                "Project subtasks are **off** by default (fast load). Set **`ASANA_PROJECT_INCLUDE_SUBTASKS=true`** "
                "to walk subtasks, or use **workspace** scope for assignee tasks including subtasks without that."
            )
        refresh = st.button("Refresh from Asana")
        if refresh:
            log_ui_event(sid, "refresh_clicked")

        ws_disp = resolve_workspace()
        tok_disp = resolve_token()
        if tok_disp and ws_disp:
            st.success("Live mode: credentials found.")
        else:
            st.warning(
                "Demo mode: add **ASANA_ACCESS_TOKEN** and **ASANA_WORKSPACE_GID** to "
                "`.env` (local) or Streamlit secrets (cloud)."
            )
            st.caption(f"Workspace GID set: **{bool(ws_disp)}** · Token set: **{bool(tok_disp)}**")

        err = st.session_state.get("asana_last_error")
        if err:
            with st.expander("Last Asana error", expanded=False):
                st.code(err, language="text")

    ws = resolve_workspace()
    tok = resolve_token()
    proj = get_task_fetch_project_gid(_secret("ASANA_PROJECT_GID"))

    data_mode = "demo"
    brand_tasks: dict[str, list[dict[str, Any]]] = mock_tasks_by_brand()

    if tok and ws:
        need_fetch = refresh or (st.session_state.get("tasks_by_brand") is None)
        if need_fetch:
            log_ui_event(sid, "asana_fetch_start", refresh=bool(refresh))
            try:
                with st.spinner("Loading tasks from Asana…"):
                    result = fetch_active_tasks_for_dashboard(tok, ws, project_gid=proj)
                brand_tasks = result.tasks_by_brand
                st.session_state.tasks_by_brand = brand_tasks
                st.session_state.asana_missing_assignees = tuple(result.missing_assignees)
                st.session_state.asana_resolved_assignees = tuple(result.resolved_assignees)
                st.session_state.asana_tasks_in_scope = result.tasks_in_scope
                st.session_state.asana_sample_titles = tuple(result.sample_task_titles)
                st.session_state.asana_scope_includes_unassigned = bool(
                    result.scope_includes_unassigned_incomplete
                )
                st.session_state.asana_last_error = None
                data_mode = "live"
                total = sum(len(v) for v in brand_tasks.values())
                log_ui_event(
                    sid,
                    "asana_fetch_ok",
                    task_rows_total=total,
                    tasks_in_scope=result.tasks_in_scope,
                    brands=list(brand_tasks.keys()),
                    assignees_resolved=[p[0] for p in result.resolved_assignees],
                )
            except Exception as e:
                msg = f"{type(e).__name__}: {e}"
                st.session_state.asana_last_error = msg
                st.session_state.tasks_by_brand = mock_tasks_by_brand()
                st.session_state.asana_missing_assignees = ()
                st.session_state.asana_resolved_assignees = ()
                st.session_state.asana_tasks_in_scope = None
                st.session_state.asana_sample_titles = ()
                st.session_state.asana_scope_includes_unassigned = False
                brand_tasks = st.session_state.tasks_by_brand
                data_mode = "error"
                prefix = "Asana configuration" if isinstance(e, AsanaConfigError) else "Asana request"
                st.error(f"{prefix}: {e}")
                log_ui_event(sid, "asana_fetch_error", error=msg[:500])
        else:
            brand_tasks = st.session_state.tasks_by_brand or mock_tasks_by_brand()
            data_mode = "live"
    else:
        st.session_state.tasks_by_brand = None
        st.session_state.asana_tasks_in_scope = None
        st.session_state.asana_sample_titles = ()
        if not st.session_state.get("demo_mode_logged"):
            log_ui_event(sid, "demo_mode", token_set=bool(tok), workspace_set=bool(ws))
            st.session_state.demo_mode_logged = True

    scope_for_ui = st.session_state.get("asana_tasks_in_scope")
    if scope_for_ui is None or data_mode == "demo":
        scope_for_ui = sum(len(v) for v in brand_tasks.values())
    scope_note = ""
    if data_mode == "live" and st.session_state.get("asana_scope_includes_unassigned"):
        scope_note = " · Project scope includes **unassigned** open tasks (see sidebar)."
    st.caption(
        f"Data: **{data_mode}** · **{scope_for_ui}** incomplete task(s) in scope before brand filter · "
        f"Keywords in `integrations/asana/brands.py`. "
        f"Events → `logs/ui_events.txt`."
        f"{scope_note}"
    )
    if (
        data_mode == "live"
        and st.session_state.get("asana_sample_titles")
        and scope_for_ui > 0
    ):
        with st.expander("Sample task titles in scope (debug)", expanded=False):
            for t in st.session_state.asana_sample_titles:
                st.text(t or "(untitled)")
    miss = st.session_state.get("asana_missing_assignees") or ()
    if miss:
        st.warning(
            "These names were **not** found in the workspace user list (check spelling vs Asana profile): "
            + ", ".join(f"**{m}**" for m in miss)
        )

    st.markdown("##### Brand")
    brand = st.radio(
        "Brand",
        options=list(BRAND_KEYWORDS.keys()),
        horizontal=True,
        key="brand_nav",
        label_visibility="collapsed",
        on_change=_on_brand_change,
    )
    st.subheader(brand)
    render_brand_content(
        brand,
        brand_tasks.get(brand, []),
        tasks_in_scope=int(scope_for_ui),
    )


if __name__ == "__main__":
    main()
