"""
Regression: Velo QA task (production Asana).

Canonical URL (Apr 2026):
https://app.asana.com/1/10469352526629/project/1205432657795982/task/1213894553177371

This task is a **subtask** of a parent in the default dashboard project; project list APIs
omit subtasks unless we walk GET /tasks/{parent}/subtasks.

These tests use a **fixture** snapshot (no live API). Run `pytest` on every change.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from integrations.asana.brands import BRAND_KEYWORDS, filter_tasks_for_brand, task_search_text
from integrations.asana.client import _expand_project_tasks_with_subtasks

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "asana" / "task_velo_qa_1213894553177371.json"

VELO_QA_TASK_GID = "1213894553177371"
VELO_QA_PARENT_GID = "1213103154970472"


@pytest.fixture
def velo_qa_task() -> dict:
    raw = _FIXTURE.read_text(encoding="utf-8")
    return json.loads(raw)


def test_fixture_file_exists() -> None:
    assert _FIXTURE.is_file(), f"Missing fixture: {_FIXTURE}"


def test_velo_qa_task_gid_constant_matches_fixture(velo_qa_task: dict) -> None:
    assert velo_qa_task["gid"] == VELO_QA_TASK_GID


def test_velo_qa_task_search_text_contains_velo_keyword(velo_qa_task: dict) -> None:
    hay = task_search_text(velo_qa_task)
    assert "velo" in hay


def test_velo_qa_task_matches_velo_brand(velo_qa_task: dict) -> None:
    from integrations.asana.brands import brand_matches_task

    assert brand_matches_task("Velo", velo_qa_task) is True


def test_velo_qa_task_appears_in_velo_tab_when_in_raw_list(velo_qa_task: dict) -> None:
    raw = [velo_qa_task]
    velo_tasks = filter_tasks_for_brand(raw, "Velo")
    assert len(velo_tasks) == 1
    assert velo_tasks[0]["gid"] == VELO_QA_TASK_GID


def test_velo_qa_task_not_double_counted_other_brands(velo_qa_task: dict) -> None:
    raw = [velo_qa_task]
    for brand in BRAND_KEYWORDS:
        n = len(filter_tasks_for_brand(raw, brand))
        if brand == "Velo":
            assert n == 1
        else:
            assert n == 0


def test_expand_project_tasks_includes_velo_subtask_after_parent(
    monkeypatch: pytest.MonkeyPatch,
    velo_qa_task: dict,
) -> None:
    """Subtask merge must include gid 1213894553177371 when parent lists num_subtasks > 0."""

    def fake_subtasks(
        session: object,
        parent_gid: str,
    ) -> list[dict]:
        if parent_gid == VELO_QA_PARENT_GID:
            return [velo_qa_task]
        return []

    monkeypatch.setattr(
        "integrations.asana.client._paginate_subtasks_for_task",
        fake_subtasks,
    )

    parent_row = {
        "gid": VELO_QA_PARENT_GID,
        "name": "TRAD | Brand Trading Actions - VELO",
        "completed": False,
        "num_subtasks": 10,
        "assignee": {"gid": "1197350665112878", "name": "Cormac Folan"},
    }

    out = _expand_project_tasks_with_subtasks(
        [parent_row],
        max_depth=5,
        token="test-token",
    )
    gids = {str(t.get("gid")) for t in out}
    assert VELO_QA_TASK_GID in gids
    assert VELO_QA_PARENT_GID in gids
