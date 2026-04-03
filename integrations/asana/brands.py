"""Brand → keyword lists for matching Asana task titles and descriptions."""

from __future__ import annotations

import re
from typing import Iterable

# Tab order in the Streamlit UI (keys must match).
BRAND_KEYWORDS: dict[str, list[str]] = {
    "ZYN": ["zyn"],
    "Velo": ["velo"],
    "Nordic Spirit": [
        "nordic spirit",
        "nordicspirit",
        "nordic-spirit",
    ],
    "FUMi": ["fumi"],
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _strip_html(html: str) -> str:
    if not html:
        return ""
    return re.sub(r"<[^>]+>", " ", html)


def task_search_blob(name: str, notes: str | None, html_notes: str | None) -> str:
    """Single lowercase string used for substring matching."""
    parts = [name or "", notes or "", _strip_html(html_notes or "")]
    return _normalize(" ".join(parts))


def brand_matches_task(brand: str, name: str, notes: str | None, html_notes: str | None) -> bool:
    """True if any brand keyword appears in the task name or description."""
    keywords = BRAND_KEYWORDS.get(brand)
    if not keywords:
        return False
    hay = task_search_blob(name, notes, html_notes)
    return any(_normalize(k) in hay for k in keywords)


def filter_tasks_for_brand(
    tasks: Iterable[dict],
    brand: str,
) -> list[dict]:
    """Keep tasks that are not completed and match the brand keywords."""
    out: list[dict] = []
    for t in tasks:
        if t.get("completed"):
            continue
        name = t.get("name") or ""
        notes = t.get("notes")
        html_notes = t.get("html_notes")
        if brand_matches_task(brand, name, notes, html_notes):
            out.append(t)
    return out
