"""
Environment variable names for touchpoints connectors (no secrets in code).

Populate via `.env` locally and GitHub Actions secrets in CI.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class TouchpointsEnv:
    """Optional config loaded from os.environ."""

    google_oauth_client_id: str | None
    google_oauth_client_secret: str | None
    gmail_refresh_token_dave: str | None
    gmail_refresh_token_cormac: str | None
    gmail_refresh_token_wholesale: str | None
    slack_bot_token: str | None
    slack_signing_secret: str | None
    openai_api_key: str | None
    anthropic_api_key: str | None
    database_url: str | None

    @classmethod
    def from_environ(cls) -> TouchpointsEnv:
        return cls(
            google_oauth_client_id=os.environ.get("GOOGLE_OAUTH_CLIENT_ID"),
            google_oauth_client_secret=os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET"),
            gmail_refresh_token_dave=os.environ.get("GMAIL_REFRESH_TOKEN_DAVE"),
            gmail_refresh_token_cormac=os.environ.get("GMAIL_REFRESH_TOKEN_CORMAC"),
            gmail_refresh_token_wholesale=os.environ.get("GMAIL_REFRESH_TOKEN_WHOLESALE"),
            slack_bot_token=os.environ.get("SLACK_BOT_TOKEN"),
            slack_signing_secret=os.environ.get("SLACK_SIGNING_SECRET"),
            openai_api_key=os.environ.get("OPENAI_API_KEY"),
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
            database_url=os.environ.get("DATABASE_URL"),
        )
