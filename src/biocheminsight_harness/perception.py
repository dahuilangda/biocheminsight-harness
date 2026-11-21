"""Quality-aware perception routing.

Routes each page through the best perception channel:
  paddle VL-1.6 (fast, deterministic) tried first.
  If the result lacks notation markers or content density, the page is
  escalated to agent vision (the agent reads the rendered image directly).

Quality metrics detect:
  - empty/poor content
  - degenerate repetition (decoder loops)
  - missing notation markers (ac-, SEQ ID NO:, Compound N)
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


class PaddleOcrBackend:
    def __init__(self, base_url: str | None = None, timeout: float = 600.0):
        self.base_url = (base_url or paddleocr_url()).rstrip("/")
        self.timeout = timeout

    def read_pages(self, pdf_path: str | Path, page_start: int,
                   page_end: int, lang: str = "en") -> dict[int, str]:
        with open(pdf_path, "rb") as handle:
            response = httpx.post(
                f"{self.base_url}/v1/pdf-to-markdown",
                files={"file": handle},
                data={"page_start": str(page_start),
                      "page_end": str(page_end),
                      "lang": lang,
                      "return_raw": "false"},
                timeout=self.timeout,
            )
        response.raise_for_status()
        job_id = response.json().get("job_id")
        if not job_id:
            raise RuntimeError("paddle submit returned no job id")
        import time
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            status = httpx.get(f"{self.base_url}/v1/jobs/{job_id}",
                               timeout=30.0).json()
            state = str(status.get("status") or "").lower()
            if state == "completed":
                break
            if state == "failed":
                raise RuntimeError(f"paddle job {job_id} failed")
            time.sleep(2.0)
        else:
            raise TimeoutError(f"paddle job {job_id} timed out")
        result = httpx.get(f"{self.base_url}/v1/jobs/{job_id}/result",
                           timeout=60.0).json()
        out: dict[int, str] = {}
        for item in result.get("pages") or []:
            page_number = int(item.get("page_number") or 0)
            out[page_number] = str(item.get("markdown") or "")
        return out
