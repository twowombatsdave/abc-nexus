"""Sample tasks for local UI testing when Asana env/secrets are not configured."""

from __future__ import annotations

from integrations.asana.brands import BRAND_KEYWORDS, filter_tasks_for_brand


def build_mock_task(
    gid: str,
    name: str,
    *,
    notes: str = "",
    completed: bool = False,
    assignee_name: str = "Alan Doran",
) -> dict:
    return {
        "gid": gid,
        "name": name,
        "notes": notes,
        "html_notes": "",
        "completed": completed,
        "due_on": None,
        "permalink_url": f"https://app.asana.com/0/0/{gid}",
        "assignee": {"gid": f"user-{gid}", "name": assignee_name},
    }


def mock_tasks_universe() -> list[dict]:
    """A small pool of tasks covering brands + one non-matching row."""
    return [
        build_mock_task(
            "m1",
            "Killa — retailer follow-up",
            notes="Confirm listing for Killa variant.",
        ),
        build_mock_task(
            "m2",
            "SYX pipeline",
            notes="Sync on SYX POS materials.",
            assignee_name="Cormac Folan",
        ),
        build_mock_task(
            "m3",
            "ELF assets review",
            notes="ELF campaign copy.",
        ),
        build_mock_task(
            "m4",
            "Clew compliance",
            notes="Clew labeling notes.",
        ),
        build_mock_task(
            "m5",
            "FEDRS launch checklist",
            notes="fedrs regulatory.",
        ),
        build_mock_task(
            "m6",
            "LUMi packaging",
            notes="lumi SKU update.",
        ),
        build_mock_task(
            "m7",
            "Ubbs retailer",
            notes="ubbs listing.",
        ),
        build_mock_task(
            "m8",
            "Unrelated task",
            notes="No brand keywords here.",
        ),
    ]


def mock_tasks_by_brand() -> dict[str, list[dict]]:
    raw = mock_tasks_universe()
    return {brand: filter_tasks_for_brand(raw, brand) for brand in BRAND_KEYWORDS}
