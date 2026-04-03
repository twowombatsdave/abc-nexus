"""Tests for touchpoints domain models."""

from __future__ import annotations

from datetime import datetime, timezone

from integrations.touchpoints.models import (
    InteractionKind,
    TouchpointEvent,
    TouchpointSource,
)


def test_touchpoint_event_frozen() -> None:
    e = TouchpointEvent(
        brand_slug="ZYN",
        occurred_at=datetime(2026, 3, 21, 12, 0, tzinfo=timezone.utc),
        kind=InteractionKind.CALL,
        source=TouchpointSource.SLACK,
        title="Call with buyer",
        external_ref="C123.1234567890",
        summary="Discussed pricing",
    )
    assert e.brand_slug == "ZYN"
    assert e.kind == InteractionKind.CALL
