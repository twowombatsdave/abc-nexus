"""Tests for brand keyword matching on synthetic task payloads."""

from __future__ import annotations

from integrations.asana.brands import brand_matches_task, filter_tasks_for_brand
from integrations.asana.mock_tasks import mock_tasks_by_brand, mock_tasks_universe


def test_brand_matches_case_insensitive() -> None:
    assert brand_matches_task("Killa", "Review killa SKU", None, None) is True
    assert brand_matches_task("SYX", "SYX roadmap", None, None) is True
    assert brand_matches_task("Ubbs", "Nothing here", None, None) is False


def test_legacy_brands() -> None:
    assert brand_matches_task("ZYN", "Review zyn SKU", None, None) is True
    assert brand_matches_task("Velo", "VELO roadmap", None, None) is True
    assert brand_matches_task("Nordic Spirit", "nordicspirit pack", None, None) is True
    assert brand_matches_task("FUMi", "fumi labels", None, None) is True


def test_elf_word_boundary() -> None:
    assert brand_matches_task("ELF", "ELF launch pack", None, None) is True
    assert brand_matches_task("ELF", "Bookshelf install", None, None) is False


def test_html_notes_searched() -> None:
    assert (
        brand_matches_task(
            "LUMi",
            "Task",
            None,
            "<body>LUMi mention in rich text</body>",
        )
        is True
    )


def test_filter_excludes_completed() -> None:
    raw = [
        {"name": "Killa open", "notes": "", "html_notes": "", "completed": False},
        {"name": "Killa done", "notes": "", "html_notes": "", "completed": True},
    ]
    out = filter_tasks_for_brand(raw, "Killa")
    assert len(out) == 1
    assert out[0]["name"] == "Killa open"


def test_mock_universe_splits_by_brand() -> None:
    by = mock_tasks_by_brand()
    assert set(by.keys()) == {
        "ZYN",
        "Velo",
        "Nordic Spirit",
        "FUMi",
        "Killa",
        "SYX",
        "ELF",
        "Clew",
        "FEDRS",
        "LUMi",
        "Ubbs",
    }
    assert len(mock_tasks_universe()) == 12
    assert sum(len(v) for v in by.values()) == 11  # one task has no brand keywords


def test_get_project_gid_default(monkeypatch) -> None:
    from integrations.asana.client import DEFAULT_PROJECT_GID, get_project_gid

    monkeypatch.delenv("ASANA_PROJECT_GID", raising=False)
    assert get_project_gid(None) == DEFAULT_PROJECT_GID
