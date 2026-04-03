"""Brand → keyword lists for matching Asana task text (name, notes, HTML body, custom fields)."""

from __future__ import annotations

import re
from typing import Any, Iterable

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
    "Killa": ["killa"],
    "SYX": ["syx"],
    "ELF": ["elf"],  # matched with word boundaries (see brand_matches_task)
    "Clew": ["clew"],
    "FEDRS": ["fedrs", "fedr"],
    "LUMi": ["lumi"],
    "Ubbs": ["ubbs"],
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _strip_html(html: str) -> str:
    if not html:
        return ""
    return re.sub(r"<[^>]+>", " ", html)


def task_search_blob(name: str, notes: str | None, html_notes: str | None) -> str:
    """Single lowercase string from title + plain notes + HTML body (tags stripped)."""
    parts = [name or "", notes or "", _strip_html(html_notes or "")]
    return _normalize(" ".join(parts))


def _custom_fields_search_text(fields: Any) -> str:
    """Flatten Asana custom field labels and values into searchable plain text."""
    if not isinstance(fields, list):
        return ""
    parts: list[str] = []
    for f in fields:
        if not isinstance(f, dict):
            continue
        for key in ("name", "display_value", "text_value"):
            v = f.get(key)
            if v is not None and v != "":
                parts.append(str(v))
        nv = f.get("number_value")
        if nv is not None:
            parts.append(str(nv))
        ev = f.get("enum_value")
        if isinstance(ev, dict) and ev.get("name"):
            parts.append(str(ev["name"]))
        mevs = f.get("multi_enum_values")
        if isinstance(mevs, list):
            for m in mevs:
                if isinstance(m, dict) and m.get("name"):
                    parts.append(str(m["name"]))
    return " ".join(parts)


def task_search_text(task: dict[str, Any]) -> str:
    """
    Normalized searchable text for keyword matching: title, notes, HTML notes,
    and custom field names/values (see ``TASK_OPT_FIELDS`` in the Asana client).
    """
    name = task.get("name") or ""
    notes = task.get("notes")
    html_notes = task.get("html_notes")
    base = task_search_blob(name, notes, html_notes)
    extra = _custom_fields_search_text(task.get("custom_fields"))
    return _normalize(f"{base} {extra}".strip())


def brand_matches_task(brand: str, task: dict[str, Any]) -> bool:
    """True if any brand keyword appears in the task's searchable text."""
    keywords = BRAND_KEYWORDS.get(brand)
    if not keywords:
        return False
    hay = task_search_text(task)
    if brand == "ELF":
        return bool(re.search(r"\belf\b", hay, re.IGNORECASE))
    return any(_normalize(k) in hay for k in keywords)


def filter_tasks_for_brand(
    tasks: Iterable[dict],
    brand: str,
) -> list[dict]:
    """Keep tasks that are not completed and match the brand keywords."""
    out: list[dict] = []
    for t in tasks:
        if t.get("completed") is True:
            continue
        if brand_matches_task(brand, t):
            out.append(t)
    return out
