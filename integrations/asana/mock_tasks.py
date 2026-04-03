"""Sample tasks for local UI testing when Asana env/secrets are not configured."""

from __future__ import annotations

from integrations.asana.brands import BRAND_KEYWORDS, filter_tasks_for_brand


def build_mock_task(
    gid: str,
    name: str,
    *,
    notes: str = "",
    completed: bool = False,
) -> dict:
    return {
        "gid": gid,
        "name": name,
        "notes": notes,
        "html_notes": "",
        "completed": completed,
        "due_on": None,
        "permalink_url": f"https://app.asana.com/0/0/{gid}",
    }


def mock_tasks_universe() -> list[dict]:
    """A small pool of tasks covering all four brands (incomplete)."""
    return [
        build_mock_task(
            "m1",
            "ZYN — retailer follow-up",
            notes="Confirm listing for ZYN variant.",
        ),
        build_mock_task(
            "m2",
            "Velo pipeline",
            notes="Sync with team on velo POS materials.",
        ),
        build_mock_task(
            "m3",
            "Nordic Spirit assets",
            notes="nordic spirit campaign copy review.",
        ),
        build_mock_task(
            "m4",
            "FUMi compliance",
            notes="Check FUMi labeling notes from legal.",
        ),
        build_mock_task(
            "m5",
            "Unrelated task",
            notes="No brand keywords here.",
        ),
    ]


def mock_tasks_by_brand() -> dict[str, list[dict]]:
    raw = mock_tasks_universe()
    return {brand: filter_tasks_for_brand(raw, brand) for brand in BRAND_KEYWORDS}
