"""Tests for project-scoped task filtering (assignee gids)."""

from __future__ import annotations

from integrations.asana.client import (
    _filter_project_tasks_for_assignees,
    _is_task_incomplete,
    _task_assignee_gid,
    project_include_unassigned_from_env,
)


def test_task_assignee_gid() -> None:
    assert _task_assignee_gid({"assignee": {"gid": "99", "name": "X"}}) == "99"
    assert _task_assignee_gid({"assignee": None}) is None
    assert _task_assignee_gid({}) is None


def test_is_task_incomplete() -> None:
    assert _is_task_incomplete({"completed": False}) is True
    assert _is_task_incomplete({"completed": None}) is True
    assert _is_task_incomplete({"completed": True}) is False


def test_project_include_unassigned_default_off(monkeypatch) -> None:
    monkeypatch.delenv("ASANA_PROJECT_INCLUDE_UNASSIGNED", raising=False)
    assert project_include_unassigned_from_env() is False
    monkeypatch.setenv("ASANA_PROJECT_INCLUDE_UNASSIGNED", "true")
    assert project_include_unassigned_from_env() is True


def test_filter_project_tasks_for_assignees() -> None:
    allowed = {"10", "20"}
    raw = [
        {"gid": "a", "completed": False, "assignee": None},
        {"gid": "b", "completed": False, "assignee": {"gid": "10"}},
        {"gid": "c", "completed": True, "assignee": None},
        {"gid": "d", "completed": False, "assignee": {"gid": "99"}},
    ]
    strict = _filter_project_tasks_for_assignees(raw, allowed, include_unassigned=False)
    assert [t["gid"] for t in strict] == ["b"]

    loose = _filter_project_tasks_for_assignees(raw, allowed, include_unassigned=True)
    assert [t["gid"] for t in loose] == ["a", "b"]
