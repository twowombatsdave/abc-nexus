"""
ABC dashboard — Asana outstanding tasks by brand (ZYN, Velo, Nordic Spirit, FUMi).

Environment (or Streamlit Cloud secrets with the same names):
  ASANA_ACCESS_TOKEN or ASANA_PAT — Personal Access Token
  ASANA_WORKSPACE_GID — workspace GID (required for live data)
  ASANA_PROJECT_GID — optional; limit tasks to one project

Run: python -m streamlit run hello_world.py
"""

from __future__ import annotations

import os
from typing import Any

import pandas as pd
import streamlit as st

from integrations.asana.brands import BRAND_KEYWORDS
from integrations.asana.client import (
    AsanaConfigError,
    fetch_active_tasks_for_dashboard,
    get_asana_token,
    project_gid_from_env,
    workspace_gid_from_env,
)
from integrations.asana.mock_tasks import mock_tasks_by_brand

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


@st.cache_data(ttl=120, show_spinner="Loading tasks from Asana…")
def _cached_asana_fetch(
    workspace_gid: str,
    project_gid: str | None,
    refresh_token: int,
) -> dict[str, list[dict[str, Any]]]:
    """refresh_token bumps cache when the user clicks Refresh."""
    token = resolve_token()
    if not token:
        raise AsanaConfigError("missing token")
    return fetch_active_tasks_for_dashboard(
        token,
        workspace_gid,
        project_gid=project_gid,
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


def render_tab_content(brand: str, tasks: list[dict[str, Any]]) -> None:
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
    with st.sidebar:
        st.title("ABC System")
        st.caption("Outstanding Asana tasks by brand keyword.")
        refresh = st.button("Refresh from Asana")
        if refresh:
            st.session_state["asana_refresh"] = st.session_state.get("asana_refresh", 0) + 1
        bump = int(st.session_state.get("asana_refresh", 0))

        ws = resolve_workspace()
        tok = resolve_token()
        if tok and ws:
            st.success("Live mode: credentials found.")
        else:
            st.warning("Demo mode: set **ASANA_ACCESS_TOKEN** and **ASANA_WORKSPACE_GID** (or Streamlit secrets).")

    ws = resolve_workspace()
    tok = resolve_token()
    proj = project_gid_from_env() or _secret("ASANA_PROJECT_GID")

    data_mode = "demo"
    brand_tasks: dict[str, list[dict[str, Any]]] = mock_tasks_by_brand()

    if tok and ws:
        try:
            brand_tasks = _cached_asana_fetch(ws, proj, bump)
            data_mode = "live"
        except AsanaConfigError:
            brand_tasks = mock_tasks_by_brand()
            data_mode = "demo"
        except Exception as e:
            st.error(f"Asana request failed: {e}")
            brand_tasks = mock_tasks_by_brand()
            data_mode = "error"

    st.caption(
        f"Data: **{data_mode}** · Active tasks assigned to **you** in the workspace, "
        f"filtered by brand keywords (see `integrations/asana/brands.py`)."
    )

    tab_labels = list(BRAND_KEYWORDS.keys())
    tabs = st.tabs(tab_labels)
    for tab, label in zip(tabs, tab_labels, strict=True):
        with tab:
            st.subheader(f"{label}")
            render_tab_content(label, brand_tasks.get(label, []))


if __name__ == "__main__":
    main()
