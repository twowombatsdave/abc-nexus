"""
ABC dashboard — Asana outstanding tasks by brand (ZYN, Velo, Nordic Spirit, FUMi).

Environment (or Streamlit Cloud secrets with the same names):
  ASANA_ACCESS_TOKEN or ASANA_PAT — Personal Access Token
  ASANA_WORKSPACE_GID — workspace GID (required for live data)
  ASANA_PROJECT_GID — optional; limit tasks to one project

Local dev: copy .env.example to .env in this folder (never commit .env),
  or run: powershell -ExecutionPolicy Bypass -File scripts/init_local_env.ps1
  Then verify: python scripts/verify_asana_connection.py

Run: python -m streamlit run hello_world.py

UI events append to logs/ui_events.jsonl (see integrations/ui_logging.py).
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from integrations.asana.brands import BRAND_KEYWORDS
from integrations.asana.client import (
    fetch_active_tasks_for_dashboard,
    get_asana_token,
    project_gid_from_env,
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


def tasks_to_dataframe(tasks: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for t in tasks:
        rows.append(
            {
                "Task": t.get("name") or "",
                "Due": t.get("due_on") or "",
                "Link": t.get("permalink_url") or "",
            }
        )
    return pd.DataFrame(rows)


def render_brand_content(brand: str, tasks: list[dict[str, Any]]) -> None:
    if not tasks:
        st.info(f"No active tasks matched **{brand}** keywords in title or description.")
        return
    df = tasks_to_dataframe(tasks)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Link": st.column_config.LinkColumn("Open in Asana", display_text="Open"),
        },
    )


def main() -> None:
    _log_session_start_once()
    sid = _session_id()

    with st.sidebar:
        st.title("ABC System")
        st.caption("Outstanding Asana tasks by brand keyword.")
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
    proj = project_gid_from_env() or _secret("ASANA_PROJECT_GID")

    data_mode = "demo"
    brand_tasks: dict[str, list[dict[str, Any]]] = mock_tasks_by_brand()

    if tok and ws:
        need_fetch = refresh or (st.session_state.get("tasks_by_brand") is None)
        if need_fetch:
            log_ui_event(sid, "asana_fetch_start", refresh=bool(refresh))
            try:
                with st.spinner("Loading tasks from Asana…"):
                    brand_tasks = fetch_active_tasks_for_dashboard(
                        tok, ws, project_gid=proj
                    )
                st.session_state.tasks_by_brand = brand_tasks
                st.session_state.asana_last_error = None
                data_mode = "live"
                total = sum(len(v) for v in brand_tasks.values())
                log_ui_event(
                    sid,
                    "asana_fetch_ok",
                    task_rows_total=total,
                    brands=list(brand_tasks.keys()),
                )
            except Exception as e:
                msg = f"{type(e).__name__}: {e}"
                st.session_state.asana_last_error = msg
                st.session_state.tasks_by_brand = mock_tasks_by_brand()
                brand_tasks = st.session_state.tasks_by_brand
                data_mode = "error"
                st.error(f"Asana request failed: {e}")
                log_ui_event(sid, "asana_fetch_error", error=msg[:500])
        else:
            brand_tasks = st.session_state.tasks_by_brand or mock_tasks_by_brand()
            data_mode = "live"
    else:
        st.session_state.tasks_by_brand = None
        if not st.session_state.get("demo_mode_logged"):
            log_ui_event(sid, "demo_mode", token_set=bool(tok), workspace_set=bool(ws))
            st.session_state.demo_mode_logged = True

    st.caption(
        f"Data: **{data_mode}** · Active tasks assigned to **you** in the workspace, "
        f"filtered by brand keywords (see `integrations/asana/brands.py`). "
        f"Events → `logs/ui_events.jsonl`."
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
    render_brand_content(brand, brand_tasks.get(brand, []))


if __name__ == "__main__":
    main()
