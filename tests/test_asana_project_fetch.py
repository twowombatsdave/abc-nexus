"""Tests for project-scoped task filtering (assignee gids)."""

from __future__ import annotations

import requests

from integrations.asana.client import (
    _expand_project_tasks_with_subtasks,
    _filter_project_tasks_for_assignees,
    _is_task_incomplete,
    _task_assignee_gid,
    _task_is_subtask,
    dashboard_subtasks_only_from_env,
    project_include_subtasks_from_env,
    project_include_unassigned_from_env,
    project_should_expand_subtasks,
)


def test_task_assignee_gid() -> None:
    assert _task_assignee_gid({"assignee": {"gid": "99", "name": "X"}}) == "99"
    assert _task_assignee_gid({"assignee": None}) is None
    assert _task_assignee_gid({}) is None


def test_is_task_incomplete() -> None:
    assert _is_task_incomplete({"completed": False}) is True
    assert _is_task_incomplete({"completed": None}) is True
    assert _is_task_incomplete({"completed": True}) is False


def test_project_include_subtasks_default_on(monkeypatch) -> None:
    monkeypatch.delenv("ASANA_PROJECT_INCLUDE_SUBTASKS", raising=False)
    assert project_include_subtasks_from_env() is True
    monkeypatch.setenv("ASANA_PROJECT_INCLUDE_SUBTASKS", "false")
    assert project_include_subtasks_from_env() is False


def test_dashboard_subtasks_only_default_on(monkeypatch) -> None:
    monkeypatch.delenv("ASANA_DASHBOARD_SUBTASKS_ONLY", raising=False)
    assert dashboard_subtasks_only_from_env() is True
    monkeypatch.setenv("ASANA_DASHBOARD_SUBTASKS_ONLY", "false")
    assert dashboard_subtasks_only_from_env() is False


def test_task_is_subtask() -> None:
    assert _task_is_subtask({"parent": {"gid": "1"}}) is True
    assert _task_is_subtask({"parent": None}) is False
    assert _task_is_subtask({}) is False


def test_project_should_expand_for_subtasks_only_dashboard(monkeypatch) -> None:
    monkeypatch.delenv("ASANA_DASHBOARD_SUBTASKS_ONLY", raising=False)
    assert project_should_expand_subtasks("1209401086303491") is True
    monkeypatch.setenv("ASANA_DASHBOARD_SUBTASKS_ONLY", "false")
    monkeypatch.setenv("ASANA_PROJECT_INCLUDE_SUBTASKS", "false")
    assert project_should_expand_subtasks("1209401086303491") is False
    monkeypatch.setenv("ASANA_PROJECT_INCLUDE_SUBTASKS", "true")
    assert project_should_expand_subtasks("1209401086303491") is True


def test_expand_project_tasks_with_subtasks(monkeypatch) -> None:
    def fake_subtasks(
        session: requests.Session,
        parent_gid: str,
    ) -> list[dict]:
        if parent_gid == "p1":
            return [{"gid": "c1", "completed": False, "assignee": None, "num_subtasks": 0}]
        return []

    monkeypatch.setattr(
        "integrations.asana.client._paginate_subtasks_for_task",
        fake_subtasks,
    )
    out = _expand_project_tasks_with_subtasks(
        [{"gid": "p1", "name": "parent", "num_subtasks": 1}],
        max_depth=3,
        token="test-token",
    )
    gids = {t["gid"] for t in out}
    assert gids == {"p1", "c1"}


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
