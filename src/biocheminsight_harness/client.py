"""Client for a running BioChemInsight deployment (server mode)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from .config import auth_credentials, biocheminsight_url


class BioChemInsightClient:
    def __init__(self, base_url: str | None = None, timeout: float = 60.0,
                 auth: tuple[str, str] | None = None,
                 http: httpx.Client | None = None):
        self.base_url = (base_url or biocheminsight_url()).rstrip("/")
        self.timeout = timeout
        self.auth = auth if auth is not None else auth_credentials()
        self.http = http or httpx.Client(timeout=timeout, auth=self.auth, verify=False)

    def upload_pdf(self, path: str | Path) -> str:
        with open(path, "rb") as handle:
            response = self.http.post(f"{self.base_url}/api/pdfs",
                                      files={"file": handle},
                                      timeout=self.timeout * 4)
        response.raise_for_status()
        return response.json()["pdf_id"]

    def start_full_pipeline(self, pdf_id: str,
                            structure_filter_strictness: str = "strict",
                            assemble_markush: bool = True,
                            lang: str = "en") -> str:
        response = self.http.post(
            f"{self.base_url}/api/tasks/full-pipeline",
            json={"pdf_id": pdf_id,
                  "structure_filter_strictness": structure_filter_strictness,
                  "assemble_markush": assemble_markush,
                  "lang": lang},
        )
        response.raise_for_status()
        return response.json()["task_id"]



    def task(self, task_id: str) -> dict[str, Any]:
        response = self.http.get(f"{self.base_url}/api/tasks/{task_id}")
        response.raise_for_status()
        return response.json()


    def download_result(self, task_id: str, dest: str | Path) -> Path:
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with self.http.stream(
            "GET", f"{self.base_url}/api/tasks/{task_id}/download",
            timeout=self.timeout * 4,
        ) as response:
            response.raise_for_status()
            with open(dest, "wb") as handle:
                for chunk in response.iter_bytes():
                    handle.write(chunk)
        return dest
