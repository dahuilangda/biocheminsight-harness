from __future__ import annotations

import json
from pathlib import Path

import httpx

from .config import harness_url


def read_compound_labels(
    pdf_path: str, page: int, boxes: list[tuple[float, float, float, float]],
) -> dict:
    path = Path(pdf_path)
    with path.open("rb") as source:
        response = httpx.post(
            f"{harness_url().rstrip('/')}/v1/documents/compound-labels",
            files={"file": (path.name, source, "application/pdf")},
            data={"page": str(page), "boxes": json.dumps(boxes)},
            timeout=60,
            verify=False,
        )
    response.raise_for_status()
    return response.json()
