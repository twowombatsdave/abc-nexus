"""
Append-only JSONL log for Streamlit UI events (local analysis; not for production PII).

Log file: ``logs/ui_events.txt`` (gitignored). Each line is one JSON object (JSON Lines format).
Uses a ``.txt`` suffix so tooling that ignores ``*.jsonl`` (e.g. Cursor) can still read it for QA.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_logger = logging.getLogger(__name__)

_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
_LOG_FILE = _LOG_DIR / "ui_events.txt"


def log_ui_event(session_id: str, event: str, **fields: Any) -> None:
    """Record one analytics row. Never log secrets or full tokens."""
    try:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        row: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
            "event": event,
            **fields,
        }
        with _LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    except OSError as e:
        _logger.warning("ui_logging write failed: %s", e)
