"""Tests for brand keyword matching on synthetic task payloads."""

from __future__ import annotations

from integrations.asana.brands import brand_matches_task, filter_tasks_for_brand
from integrations.asana.mock_tasks import mock_tasks_by_brand, mock_tasks_universe


def test_brand_matches_case_insensitive() -> None:
    assert brand_matches_task("Killa", {"name": "Review killa SKU"}) is True
    assert brand_matches_task("SYX", {"name": "SYX roadmap"}) is True
    assert brand_matches_task("Ubbs", {"name": "Nothing here"}) is False


def test_legacy_brands() -> None:
    assert brand_matches_task("ZYN", {"name": "Review zyn SKU"}) is True
    assert brand_matches_task("Velo", {"name": "VELO roadmap"}) is True
    assert brand_matches_task("Nordic Spirit", {"name": "nordicspirit pack"}) is True
    assert brand_matches_task("FUMi", {"name": "fumi labels"}) is True


def test_elf_word_boundary() -> None:
    assert brand_matches_task("ELF", {"name": "ELF launch pack"}) is True
    assert brand_matches_task("ELF", {"name": "Bookshelf install"}) is False


def test_html_notes_searched() -> None:
    assert (
        brand_matches_task(
            "LUMi",
            {
                "name": "Task",
                "html_notes": "<body>LUMi mention in rich text</body>",
            },
        )
        is True
    )


def test_notes_only_match() -> None:
    assert brand_matches_task(
        "Killa",
        {"name": "Pricing review", "notes": "Discuss killa line extension"},
    ) is True


def test_custom_fields_searched() -> None:
    task = {
        "name": "Untitled",
        "notes": "",
        "html_notes": "",
        "custom_fields": [
            {
                "name": "Segment",
                "display_value": "ZYN Launch",
                "enum_value": {"name": "ZYN"},
            },
        ],
    }
    assert brand_matches_task("ZYN", task) is True


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
