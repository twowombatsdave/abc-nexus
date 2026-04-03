"""Unit tests for ABC mock data builders (no Streamlit runtime required)."""

from __future__ import annotations

from app import CLIENTS, TIMELINE_SOURCES, _mock_sales_data, _mock_timeline_data


def test_timeline_columns_sources_and_per_client_rows() -> None:
    df = _mock_timeline_data()
    assert list(df.columns) == ["Client", "Timestamp", "Source", "Actor", "Message"]
    assert set(df["Source"].unique()) <= set(TIMELINE_SOURCES)
    for c in CLIENTS:
        assert len(df[df["Client"] == c]) == 28


def test_timeline_deterministic() -> None:
    a = _mock_timeline_data()
    b = _mock_timeline_data()
    assert a.equals(b)


def test_sales_columns_and_shape() -> None:
    df = _mock_sales_data()
    assert list(df.columns) == ["Date", "Client", "SKU", "Revenue", "Margin", "OrderId"]
    assert len(df) == len(CLIENTS) * 180
    for c in CLIENTS:
        sub = df[df["Client"] == c]
        assert sub["SKU"].str.startswith({"Client A": "ALPHA", "Client B": "BRAVO", "Client C": "CHARLIE"}[c]).all()


def test_sales_deterministic() -> None:
    a = _mock_sales_data()
    b = _mock_sales_data()
    assert a.equals(b)
