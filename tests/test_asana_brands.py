"""Tests for brand keyword matching on synthetic task payloads."""

from __future__ import annotations

from integrations.asana.brands import brand_matches_task, filter_tasks_for_brand
from integrations.asana.mock_tasks import mock_tasks_by_brand, mock_tasks_universe


def test_brand_matches_case_insensitive() -> None:
    assert brand_matches_task("ZYN", "Review zyn SKU", None, None) is True
    assert brand_matches_task("Velo", "VELO roadmap", None, None) is True
    assert brand_matches_task("FUMi", "Nothing here", None, None) is False


def test_nordic_spirit_phrases() -> None:
    assert brand_matches_task("Nordic Spirit", "Nordic Spirit launch", None, None) is True
    assert brand_matches_task("Nordic Spirit", "nordicspirit pack", None, None) is True
    assert brand_matches_task("Nordic Spirit", "nordic-spirit", None, None) is True


def test_html_notes_searched() -> None:
    assert (
        brand_matches_task(
            "ZYN",
            "Task",
            None,
            "<body>ZYN mention in rich text</body>",
        )
        is True
    )


def test_filter_excludes_completed() -> None:
    raw = [
        {"name": "ZYN open", "notes": "", "html_notes": "", "completed": False},
        {"name": "ZYN done", "notes": "", "html_notes": "", "completed": True},
    ]
    out = filter_tasks_for_brand(raw, "ZYN")
    assert len(out) == 1
    assert out[0]["name"] == "ZYN open"


def test_mock_universe_splits_by_brand() -> None:
    by = mock_tasks_by_brand()
    assert set(by.keys()) == {"ZYN", "Velo", "Nordic Spirit", "FUMi"}
    assert len(mock_tasks_universe()) >= 5
    assert sum(len(v) for v in by.values()) == 4  # one task has no brand keywords
