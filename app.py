"""
ABC System (Always Be Closing) — V1 UI scaffolding with mock data.

Run locally: python -m streamlit run app.py
Install: pip install -r requirements-abc-app.txt
"""

from __future__ import annotations

import html
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
import streamlit as st

# --- Constants ----------------------------------------------------------------

CLIENTS: list[str] = ["Client A", "Client B", "Client C"]

TIMELINE_SOURCES: tuple[str, ...] = ("Slack", "Asana", "Meet", "WhatsApp")

# Left-border accent for each source (edit hex values to re-theme the CRM feed).
SOURCE_STYLE: dict[str, dict[str, str]] = {
    "Slack": {"border": "#2563eb", "bg": "rgba(37, 99, 235, 0.06)"},  # blue
    "Asana": {"border": "#7c3aed", "bg": "rgba(124, 58, 237, 0.08)"},  # purple
    "Meet": {"border": "#dc2626", "bg": "rgba(220, 38, 38, 0.06)"},  # red
    "WhatsApp": {"border": "#16a34a", "bg": "rgba(22, 163, 74, 0.08)"},  # green
}

SKU_PREFIXES: dict[str, str] = {
    "Client A": "ALPHA",
    "Client B": "BRAVO",
    "Client C": "CHARLIE",
}


# --- Session state --------------------------------------------------------------

def init_session_state() -> None:
    """Persist selections across Streamlit reruns."""
    if "selected_client" not in st.session_state:
        st.session_state.selected_client = CLIENTS[0]


# --- Mock data (cached: stable across widget interactions) ----------------------

def _mock_timeline_data() -> pd.DataFrame:
    """Synthetic multi-client activity feed (deterministic RNG; safe for unit tests)."""
    rng = np.random.default_rng(42)
    rows: list[dict[str, object]] = []
    base = datetime(2025, 1, 1, 9, 0, 0)

    sample_messages: dict[str, list[str]] = {
        "Slack": [
            "Shared Q4 deck — please review slides 4–7.",
            "Looping in finance for the revised forecast.",
            "Can we move the standup to 10:30?",
        ],
        "Asana": [
            "Task marked complete: onboarding checklist.",
            "Due date shifted by 2 days per client request.",
            "New subtask added under 'Launch prep'.",
        ],
        "Meet": [
            "Call ended — next sync Thursday.",
            "Recording link posted in Slack.",
            "Action items: follow up on pricing, confirm SKUs.",
        ],
        "WhatsApp": [
            "Quick question on shipment timing.",
            "Photo of pallet labels attached.",
            "Thanks — received.",
        ],
    }
    actors_pool = ["Alex (You)", "Jordan Lee", "Sam Rivera", "Priya Shah", "Chris Ortiz"]

    for client in CLIENTS:
        n = 28
        for i in range(n):
            src = TIMELINE_SOURCES[int(rng.integers(0, len(TIMELINE_SOURCES)))]
            ts = base + timedelta(
                days=int(rng.integers(0, 120)),
                hours=int(rng.integers(0, 24)),
                minutes=int(rng.integers(0, 60)),
            )
            actor = str(rng.choice(actors_pool))
            msg = str(rng.choice(sample_messages[src]))
            rows.append(
                {
                    "Client": client,
                    "Timestamp": ts,
                    "Source": src,
                    "Actor": actor,
                    "Message": msg,
                }
            )

    df = pd.DataFrame(rows)
    return df.sort_values("Timestamp", ascending=False).reset_index(drop=True)


@st.cache_data(show_spinner=False)
def generate_timeline_data() -> pd.DataFrame:
    return _mock_timeline_data()


def _mock_sales_data() -> pd.DataFrame:
    """Synthetic sales rows: Date, Client, SKU, Revenue, Margin ($), OrderId."""
    rng = np.random.default_rng(7)
    start = date(2025, 1, 1)
    rows: list[dict[str, object]] = []

    for client in CLIENTS:
        prefix = SKU_PREFIXES[client]
        skus = [f"{prefix}-{i:03d}" for i in range(1, 9)]
        oid = 1000
        for _ in range(180):
            d = start + timedelta(days=int(rng.integers(0, 150)))
            sku = str(rng.choice(skus))
            revenue = float(rng.uniform(800, 12000))
            margin_pct = float(rng.uniform(0.12, 0.38))
            margin_d = revenue * margin_pct
            rows.append(
                {
                    "Date": d,
                    "Client": client,
                    "SKU": sku,
                    "Revenue": round(revenue, 2),
                    "Margin": round(margin_d, 2),
                    "OrderId": f"ORD-{client[:1]}-{oid}",
                }
            )
            oid += 1

    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False)
def generate_sales_data() -> pd.DataFrame:
    return _mock_sales_data()


# --- CRM timeline HTML ----------------------------------------------------------

def _timeline_card_row(row: pd.Series) -> str:
    """Build one HTML card; message body is escaped for safe embedding."""
    src = str(row["Source"])
    style = SOURCE_STYLE.get(
        src,
        {"border": "#64748b", "bg": "rgba(100, 116, 139, 0.06)"},
    )
    ts = row["Timestamp"]
    if isinstance(ts, pd.Timestamp):
        ts_s = ts.strftime("%Y-%m-%d %H:%M")
    else:
        ts_s = str(ts)[:16]

    safe_actor = html.escape(str(row["Actor"]))
    safe_src = html.escape(src)
    safe_body = html.escape(str(row["Message"]))

    # Card layout: flex row with a thick left border (color = channel).
    # The outer div uses inline styles so Streamlit markdown does not depend on a global CSS file.
    return f"""
<div class="abc-card" style="
    border-left: 6px solid {style['border']};
    background: {style['bg']};
    border-radius: 8px;
    padding: 12px 14px;
    margin-bottom: 10px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.06);
">
  <div style="display:flex; justify-content:space-between; gap:12px; flex-wrap:wrap;">
    <span style="font-weight:600; color:#0f172a;">{safe_actor}</span>
    <span style="font-size:0.85rem; color:#475569;">{ts_s}</span>
  </div>
  <div style="margin-top:4px; font-size:0.8rem; color:#334155;">
    <span style="
      display:inline-block;
      padding:2px 8px;
      border-radius:999px;
      background:rgba(15,23,42,0.06);
      font-weight:600;
    ">{safe_src}</span>
  </div>
  <div style="margin-top:8px; color:#0f172a; line-height:1.45;">{safe_body}</div>
</div>
"""


def render_crm_tab(client: str) -> None:
    """Close.io-style scrolling feed (cards, not a raw dataframe)."""
    df = generate_timeline_data()
    sub = df[df["Client"] == client].copy()

    st.subheader("Communication timeline")
    st.caption("Newest first · Colors map to source (edit SOURCE_STYLE in app.py).")

    # Optional: subtle container + typography tweaks for the feed only.
    st.markdown(
        """
<style>
  /* Scoped wrapper: keeps timeline spacing predictable inside the tab. */
  .abc-timeline-wrap { max-width: 920px; }
</style>
<div class="abc-timeline-wrap">
""",
        unsafe_allow_html=True,
    )

    if sub.empty:
        st.info("No timeline entries for this client.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    parts = [_timeline_card_row(sub.iloc[i]) for i in range(len(sub))]
    html_blob = "\n".join(parts)
    st.markdown(html_blob, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


# --- Reporting -----------------------------------------------------------------

def render_reporting_tab(client: str) -> None:
    """Filters, KPI metrics, and charts driven by mock sales data."""
    sales = generate_sales_data()
    c_df = sales[sales["Client"] == client].copy()
    if c_df.empty:
        st.warning("No sales rows for this client.")
        return

    d_min = c_df["Date"].min()
    d_max = c_df["Date"].max()
    all_skus = sorted(c_df["SKU"].unique().tolist())

    # Per-client widget keys so date bounds and SKU lists stay consistent when switching accounts.
    dr_key = f"report_date_range_{client}"
    sku_key = f"report_skus_{client}"
    last_key = "reporting_last_client"
    if st.session_state.get(last_key) != client:
        st.session_state[last_key] = client
        st.session_state[sku_key] = list(all_skus)
        st.session_state[dr_key] = (d_min, d_max)

    st.subheader("Filters")
    c1, c2 = st.columns(2)
    with c1:
        date_range = st.date_input(
            "Date range",
            value=(d_min, d_max),
            min_value=d_min,
            max_value=d_max,
            key=dr_key,
        )
    with c2:
        selected_skus = st.multiselect(
            "SKUs",
            options=all_skus,
            key=sku_key,
        )

    # Normalize date_input: single date vs range across Streamlit versions.
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_d, end_d = date_range[0], date_range[1]
    else:
        start_d = end_d = date_range  # type: ignore[assignment]

    filt = c_df[(c_df["Date"] >= start_d) & (c_df["Date"] <= end_d)]
    if selected_skus:
        filt = filt[filt["SKU"].isin(selected_skus)]
    else:
        filt = filt.iloc[0:0]

    st.subheader("Overview")
    m1, m2, m3, m4 = st.columns(4)
    total_rev = float(filt["Revenue"].sum()) if not filt.empty else 0.0
    total_margin = float(filt["Margin"].sum()) if not filt.empty else 0.0
    avg_margin_pct = (total_margin / total_rev * 100.0) if total_rev > 0 else 0.0
    active_orders = int(filt["OrderId"].nunique()) if not filt.empty else 0

    m1.metric("Total revenue", f"${total_rev:,.0f}")
    m2.metric("Total margin ($)", f"${total_margin:,.0f}")
    m3.metric("Avg margin %", f"{avg_margin_pct:.1f}%")
    m4.metric("Active orders", f"{active_orders:,}")

    st.subheader("Trends")
    if filt.empty:
        st.info("Adjust filters to see charts.")
        return

    line_df = (
        filt.groupby("Date", as_index=False)["Revenue"]
        .sum()
        .sort_values("Date")
        .set_index("Date")
    )
    bar_df = filt.groupby("SKU", as_index=False)["Revenue"].sum().sort_values(
        "Revenue", ascending=False
    )

    lc1, lc2 = st.columns(2)
    with lc1:
        st.markdown("**Revenue over time**")
        st.line_chart(line_df)
    with lc2:
        st.markdown("**Revenue by SKU**")
        st.bar_chart(bar_df.set_index("SKU"))


# --- Margin modeller -----------------------------------------------------------

def render_margin_modeller_tab() -> None:
    """What-if pricing table: scenarios derived from Base Price."""
    st.subheader("Base inputs")
    c1, c2, c3 = st.columns(3)
    with c1:
        target_margin_pct = st.number_input(
            "Target margin %",
            min_value=0.0,
            max_value=99.9,
            value=28.0,
            step=0.5,
            help="Reference target; actual % comes from price and COGS.",
        )
    with c2:
        cogs = st.number_input(
            "Current COGS ($)",
            min_value=0.0,
            value=42.0,
            step=1.0,
        )
    with c3:
        base_price = st.number_input(
            "Base price ($)",
            min_value=0.01,
            value=79.99,
            step=1.0,
        )

    multipliers = (1.0, 1.1, 1.2, 1.3)
    labels = (
        "Base price",
        "Base price + 10%",
        "Base price + 20%",
        "Base price + 30%",
    )

    rows: list[dict[str, float | str]] = []
    for label, m in zip(labels, multipliers, strict=True):
        price = float(base_price * m)
        revenue = price  # 1 unit; extend later with quantity if needed
        margin_d = revenue - float(cogs)
        margin_pct = (margin_d / revenue * 100.0) if revenue > 0 else 0.0
        rows.append(
            {
                "Scenario": label,
                "Price ($)": round(price, 2),
                "Projected revenue ($)": round(revenue, 2),
                "Projected margin ($)": round(margin_d, 2),
                "Margin %": round(margin_pct, 2),
            }
        )

    out = pd.DataFrame(rows)
    st.subheader("Scenario comparison")
    base_margin = float(out.iloc[0]["Margin %"]) if not out.empty else 0.0
    st.caption(
        f"Target margin (reference): {target_margin_pct:.1f}% · "
        f"Base scenario margin %: {base_margin:.1f}%"
    )
    st.dataframe(out, use_container_width=True, hide_index=True)


# --- Main ----------------------------------------------------------------------

def main() -> None:
    st.set_page_config(page_title="ABC System", layout="wide")
    init_session_state()

    with st.sidebar:
        st.title("ABC System")
        st.caption("Always Be Closing · V1 scaffold (mock data)")
        st.selectbox(
            "Account",
            options=CLIENTS,
            key="selected_client",
        )

    client = str(st.session_state.selected_client)
    st.header(client)

    tab_crm, tab_rep, tab_margin = st.tabs(
        ["CRM Tool", "Reporting Dashboard", "Margin Modeller"]
    )

    with tab_crm:
        render_crm_tab(client)

    with tab_rep:
        render_reporting_tab(client)

    with tab_margin:
        render_margin_modeller_tab()


if __name__ == "__main__":
    main()
