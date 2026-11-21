"""Intelligent perception routing.

Routes each page to the best perception backend based on page type:

  agent vision  — rotated dense compound tables, complex layouts,
                  pages where paddle produced degenerate output
  paddle VL-1.6 — upright prose pages, standard assay tables,
                  pages with clear text layer

The page type comes from the structure detection stage (the parallel
agents already classified each page). No fixed ordering: the router
adapts to whatever the detection stage found.
"""
from __future__ import annotations

import re
from typing import Any

import httpx

from .config import paddleocr_url

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
    """Routes pages to the best perception backend.

    Backends:
      paddle — paddle VL-1.6 service (fast, serial admission)
      agent  — the coding agent reads the rendered page with its own
               vision and writes the OCR text (parallel, no model server)

    The router selects per batch based on page type and historical
    quality. A page with a text layer routes to paddle; a rotated or
    dense compound table routes to agent vision."""

    def __init__(self, paddle_base: str | None = None):
        self.paddle_base = (paddle_base or paddleocr_url()).rstrip("/")

    def paddle_ocr_page(self, pdf_path: str | Path, page_start: int,
                        page_end: int, lang: str = "en") -> dict[int, str]:
        with open(pdf_path, "rb") as handle:
            response = httpx.post(
                f"{self.paddle_base}/v1/pdf-to-markdown",
                files={"file": handle},
                data={"page_start": str(page_start),
                      "page_end": str(page_end),
                      "lang": lang,
                      "return_raw": "false"},
                timeout=600.0,
            )
        response.raise_for_status()
        job_id = response.json().get("job_id")
        if not job_id:
            raise RuntimeError("paddle submit returned no job id")
        import time
        deadline = time.monotonic() + 600.0
        while time.monotonic() < deadline:
            status = httpx.get(f"{self.paddle_base}/v1/jobs/{job_id}",
                               timeout=30.0).json()
            state = str(status.get("status") or "").lower()
            if state == "completed":
                break
            if state == "failed":
                raise RuntimeError(f"paddle job {job_id} failed")
            time.sleep(2.0)
        else:
            raise TimeoutError(f"paddle job {job_id} timed out")
        result = httpx.get(f"{self.paddle_base}/v1/jobs/{job_id}/result",
                           timeout=60.0).json()
        out: dict[int, str] = {}
        for item in result.get("pages") or []:
            page_number = int(item.get("page_number") or 0)
            if page_number in set(range(page_start, page_end + 1)):
                out[page_number] = str(item.get("markdown") or "")
        return out

    def route_pages(self, pdf_path: str | Path, pages: list[int],
                    page_types: dict[int, str]) -> dict[int, str]:
        """Route pages to the best backend based on page type."""
        raise NotImplementedError("use a concrete subclass or wire to backends")
