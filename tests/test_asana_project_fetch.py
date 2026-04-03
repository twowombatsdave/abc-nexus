"""Tests for project-scoped task filtering (assignee gids)."""

from __future__ import annotations

from integrations.asana.client import _task_assignee_gid


def test_task_assignee_gid() -> None:
    assert _task_assignee_gid({"assignee": {"gid": "99", "name": "X"}}) == "99"
    assert _task_assignee_gid({"assignee": None}) is None
    assert _task_assignee_gid({}) is None
