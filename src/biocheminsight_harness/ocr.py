"""Serial-admission OCR client for the paddle VL-1.6 service."""
from __future__ import annotations

import time
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
        """OCR the requested pages in consecutive chunks. Chunks must be
        contiguous: non-consecutive sets are split into sub-chunks so each
        paddle job covers a contiguous page range."""
        markdowns: dict[int, str] = {}
        ordered = sorted(dict.fromkeys(int(p) for p in pages))
        chunks: list[list[int]] = []
        current: list[int] = []
        for page in ordered:
            if current and page - current[-1] > 1:
                chunks.append(current)
                current = []
            current.append(page)
        if current:
            chunks.append(current)
        for chunk in chunks:
            for sub in range(0, len(chunk), self.chunk_pages):
                sub_chunk = chunk[sub:sub + self.chunk_pages]
                markdowns.update(
                    self._chunk_markdown(pdf_path, sub_chunk, lang))
        return markdowns

    def _chunk_markdown(self, pdf_path: str | Path, chunk: list[int],
                        lang: str) -> dict[int, str]:
        """The service is an async job API: submit, poll until the job
        leaves the running state, fetch the result. Returned page numbers
        carry a service-side offset, so pages map back by sorted order."""
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
        job = response.json()
        job_id = job.get("job_id")
        if not job_id:
            raise RuntimeError(f"paddle submit returned no job id: {job}")
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
        pages = result.get("pages") or []
        numbers = [item.get("page_number") for item in pages]
        texts = [str(item.get("markdown") or "") for item in pages]
        by_page = {}
        for number, text in zip(numbers, texts):
            try:
                by_page[int(number)] = text
            except (TypeError, ValueError):
                by_page.clear()
                break
        if set(by_page) == set(chunk):
            return by_page
        # Service page numbering may be relative to the extracted range;
        # pages come back in order, so map by sorted position.
        if len(numbers) == len(chunk):
            return dict(zip(sorted(chunk), texts))
        raise RuntimeError(
            f"paddle job {job_id} returned pages {numbers} for requested "
            f"pages {chunk}")
