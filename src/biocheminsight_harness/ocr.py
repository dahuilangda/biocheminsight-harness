"""Serial-admission OCR client for the paddle VL-1.6 service."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from .config import paddleocr_url


class OcrJobCanceled(RuntimeError):
    pass


class OcrClient:
    def __init__(self, base_url: str | None = None, timeout: float = 600.0,
                 chunk_pages: int = 3):
        self.base_url = (base_url or paddleocr_url()).rstrip("/")
        self.timeout = timeout
        self.chunk_pages = chunk_pages

    def pages_markdown(self, pdf_path: str | Path, pages: list[int],
                       lang: str = "en") -> dict[int, str]:
        """OCR the requested pages in timeout-sized chunks, canceling a
        server job that outlives the client budget."""
        markdowns: dict[int, str] = {}
        ordered = sorted(dict.fromkeys(int(p) for p in pages))
        for start in range(0, len(ordered), self.chunk_pages):
            chunk = ordered[start:start + self.chunk_pages]
            markdowns.update(self._chunk_markdown(pdf_path, chunk, lang))
        return markdowns

    def _chunk_markdown(self, pdf_path: str | Path, chunk: list[int],
                        lang: str) -> dict[int, str]:
        with open(pdf_path, "rb") as handle:
            response = httpx.post(
                f"{self.base_url}/v1/pdf-to-markdown",
                files={"file": handle},
                data={"page_start": str(min(chunk)),
                      "page_end": str(max(chunk)),
                      "lang": lang,
                      "return_raw": "false"},
                timeout=self.timeout,
            )
        response.raise_for_status()
        payload = response.json()
        pages = payload.get("pages") or []
        out: dict[int, str] = {}
        for item in pages:
            page_number = int(item.get("page_number") or 0)
            if page_number in chunk:
                out[page_number] = str(item.get("markdown") or "")
        return out
