"""Tests for workspace assignee name → gid resolution."""

from __future__ import annotations

from integrations.asana.client import resolve_assignee_gids_from_user_list


def test_resolve_names_case_insensitive() -> None:
    users = [
        {"gid": "1", "name": "Alan Doran"},
        {"gid": "2", "name": "Cormac Folan"},
    ]
    gids, missing = resolve_assignee_gids_from_user_list(
        users,
        ["alan doran", "Cormac Folan"],
    )
    assert gids == ["1", "2"]
    assert missing == []


def test_missing_name_reported() -> None:
    users = [{"gid": "1", "name": "Alan Doran"}]
    gids, missing = resolve_assignee_gids_from_user_list(
        users,
        ["Alan Doran", "Nobody Here"],
    )
    assert gids == ["1"]
    assert missing == ["Nobody Here"]
