"""Domain models for touchpoint / core-interaction timeline (DB-ready)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class TouchpointSource(StrEnum):
    """Upstream system."""

    GMAIL = "gmail"
    GOOGLE_CALENDAR = "google_calendar"
    SLACK = "slack"
    MANUAL = "manual"


class InteractionKind(StrEnum):
    """Normalized interaction type for UI (Close.io–style rows)."""

    EMAIL = "email"
    MEETING = "meeting"
    CALL = "call"
    SLACK_NOTE = "slack_note"
    OTHER = "other"


@dataclass(frozen=True)
class TouchpointEvent:
    """
    One row in the customer/brand timeline.

    ``external_ref`` should be stable per source, e.g. Gmail message id, Calendar event id,
    Slack ts+channel, for idempotent upserts.
    """

    brand_slug: str
    occurred_at: datetime
    kind: InteractionKind
    source: TouchpointSource
    title: str
    external_ref: str
    summary: str | None = None
    body_excerpt: str | None = None
    raw_metadata: dict[str, Any] = field(default_factory=dict)
    llm_model: str | None = None
    id: str | None = None  # DB UUID after insert
