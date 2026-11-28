"""Route pages to text extraction or visual review."""
from __future__ import annotations

import re
from typing import Any

from .config import ocr_url
from .ocr import OcrClient, OcrJobCanceled

AGENT_PAGE_TYPES = frozenset({
    "rotated_table",
    "compound_table",
    "dense_layout",
})

_NOTATION_RE = re.compile(
    r"(?:ac-|[^a-z])-[A-Z]|SEQ ID NO|Compound \d|Example \d", re.IGNORECASE)
_DEGENERATE_RE = re.compile(r"(.{6,}?)\1{3,}", re.MULTILINE)

def assess_quality(markdown: str) -> dict[str, Any]:
    if not markdown or len(markdown) < 50:
        return {"quality": "empty", "notation_hits": 0, "chars": len(markdown)}
    notation_hits = len(_NOTATION_RE.findall(markdown))
    degenerate = bool(_DEGENERATE_RE.search(markdown))
    if degenerate:
        quality = "degenerate"
    elif notation_hits >= 2 and len(markdown) >= 200:
        quality = "good"
    elif notation_hits >= 1:
        quality = "fair"
    else:
        quality = "poor"
    return {"quality": quality, "notation_hits": notation_hits,
            "chars": len(markdown), "degenerate": degenerate}

def needs_escalation(quality: dict) -> bool:
    return quality["quality"] in ("empty", "poor", "degenerate")

def batch_requests(requests: list[dict], limit: int | None = None) -> list[dict]:
    """Next batch of pending perception requests to answer. Bounded
    because every sheet is one image in the answering agent's context;
    ordered task_name first so one batch stays inside one answer
    contract. Answered requests drop out, so re-polling yields the
    next batch."""
    if limit is None:
        from .config import perception_batch_size
        limit = perception_batch_size()
    ordered = sorted(
        requests,
        key=lambda r: (str(r.get("task_name", "")), str(r.get("request_id", ""))))
    return ordered[:max(1, int(limit))]

class PerceptionRouter:
    """Splits pages between OCR and agent vision.

    Returns OCR Markdown keyed by page plus the list of pages the
    agent must read with its own vision."""

    def __init__(self, base_url: str | None = None, chunk_pages: int = 3):
        self.client = OcrClient(
            base_url or ocr_url(), chunk_pages=chunk_pages)

    def route_pages(self, pdf_path: str, pages: list[int],
                    page_types: dict[int, str] | None = None) -> dict[str, Any]:
        page_types = page_types or {}
        ocr_pages: list[int] = []
        agent_pages: list[int] = []
        for page in sorted(dict.fromkeys(int(p) for p in pages)):
            if page_types.get(page) in AGENT_PAGE_TYPES:
                agent_pages.append(page)
            else:
                ocr_pages.append(page)
        markdowns: dict[int, str] = {}
        failed_pages: list[int] = []
        chunk = max(1, self.client.chunk_pages)
        for start in range(0, len(ocr_pages), chunk):
            batch = ocr_pages[start:start + chunk]
            try:
                markdowns.update(
                    self.client.pages_markdown(pdf_path, batch))
            except OcrJobCanceled:
                raise
            except Exception:
                failed_pages.extend(batch)
        for page in failed_pages:
            if page in markdowns:
                del markdowns[page]
        escalated = [
            page for page, text in sorted(markdowns.items())
            if needs_escalation(assess_quality(text))
        ]
        for page in escalated:
            del markdowns[page]
        return {"markdowns": markdowns,
                "agent_pages": sorted(set(agent_pages + escalated)),
                "failed_pages": sorted(failed_pages)}
