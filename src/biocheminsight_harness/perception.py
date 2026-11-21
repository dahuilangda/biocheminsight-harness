"""Intelligent perception routing.

Routes each page to the best perception backend:

  agent vision  — rotated dense compound tables, complex layouts, and
                  any page where paddle produced degenerate output
  paddle VL-1.6 — upright prose pages, standard assay tables, pages
                  with a clear text layer

The page type comes from the structure detection stage (the parallel
agents already classified each page). Paddle output that fails the
quality bar is escalated to the agent, so no fixed ordering is assumed:
the router adapts to whatever the detection stage found and to what
paddle actually produced.
"""
from __future__ import annotations

import re
from typing import Any

from .config import paddleocr_url
from .ocr import OcrClient

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


class PerceptionRouter:
    """Splits pages between paddle OCR and agent vision.

    Returns paddle markdowns keyed by page plus the list of pages the
    agent must read with its own vision."""

    def __init__(self, base_url: str | None = None, chunk_pages: int = 3):
        self.client = OcrClient(
            base_url or paddleocr_url(), chunk_pages=chunk_pages)

    def route_pages(self, pdf_path: str, pages: list[int],
                    page_types: dict[int, str] | None = None) -> dict[str, Any]:
        page_types = page_types or {}
        paddle_pages: list[int] = []
        agent_pages: list[int] = []
        for page in sorted(dict.fromkeys(int(p) for p in pages)):
            if page_types.get(page) in AGENT_PAGE_TYPES:
                agent_pages.append(page)
            else:
                paddle_pages.append(page)
        markdowns: dict[int, str] = {}
        if paddle_pages:
            markdowns = self.client.pages_markdown(pdf_path, paddle_pages)
        escalated = [
            page for page, text in sorted(markdowns.items())
            if needs_escalation(assess_quality(text))
        ]
        for page in escalated:
            del markdowns[page]
        return {"markdowns": markdowns,
                "agent_pages": sorted(agent_pages + escalated)}
