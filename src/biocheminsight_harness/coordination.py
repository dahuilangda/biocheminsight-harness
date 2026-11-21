"""File-based work coordination for parallel parsing agents.

Multiple sub-agents work the same document: batches are partitioned from
the page range, claimed atomically (mkdir is the lock), recorded as JSON,
and merged with cross-checking. The ledger is plain files so any number of
agent processes coordinate without a shared server."""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any


class BatchLedger:
    def __init__(self, run_dir: str | Path):
        self.run_dir = Path(run_dir)
        self.batches_dir = self.run_dir / "batches"
        self.claims_dir = self.run_dir / "claims"
        self.results_dir = self.run_dir / "results"
        for d in (self.batches_dir, self.claims_dir, self.results_dir):
            d.mkdir(parents=True, exist_ok=True)
        manifest = self.batches_dir / "manifest.json"
        self.batches: list[dict[str, Any]] = json.loads(
            manifest.read_text(encoding="utf-8"))

    @classmethod
    def partition(cls, run_dir: str | Path, total_pages: int,
                  pages_per_batch: int = 12) -> "BatchLedger":
        if pages_per_batch < 1:
            raise ValueError("pages_per_batch must be at least 1")
        run_dir = Path(run_dir)
        batches_dir = run_dir / "batches"
        batches_dir.mkdir(parents=True, exist_ok=True)
        manifest = batches_dir / "manifest.json"
        if not manifest.is_file():
            batches = []
            for start in range(1, total_pages + 1, pages_per_batch):
                end = min(start + pages_per_batch - 1, total_pages)
                batches.append({
                    "batch_id": f"b{start:04d}-{end:04d}",
                    "pages": list(range(start, end + 1)),
                })
            manifest.write_text(
                json.dumps(batches, ensure_ascii=False, indent=1),
                encoding="utf-8")
        return cls(run_dir)

    @staticmethod
    def _sanitize(value: str) -> str:
        return "".join(c for c in value if c.isalnum() or c in "-_.")

    def claim(self, worker: str, count: int = 1) -> list[dict[str, Any]]:
        claimed: list[dict[str, Any]] = []
        for batch in self.batches:
            if len(claimed) >= count:
                break
            token = self.claims_dir / self._sanitize(batch["batch_id"])
            try:
                token.mkdir()
            except FileExistsError:
                continue
            (token / "owner").write_text(worker, encoding="utf-8")
            batch["worker"] = worker
            claimed.append(batch)
        if claimed:
            self._record_claims(worker, claimed)
        return claimed

    def _record_claims(self, worker: str, claimed: list[dict]) -> None:
        path = self.claims_dir / f"{self._sanitize(worker)}.json"
        prior: list[str] = []
        if path.is_file():
            prior = json.loads(path.read_text(encoding="utf-8"))
        prior.extend(batch["batch_id"] for batch in claimed)
        path.write_text(json.dumps(prior), encoding="utf-8")

    def complete(self, worker: str, batch_id: str, result_path: str | Path,
                 stats: dict[str, Any] | None = None) -> None:
        records_dir = self.results_dir / "records"
        records_dir.mkdir(parents=True, exist_ok=True)
        record = {"batch_id": batch_id, "worker": worker,
                  "result": Path(result_path).name, "stats": stats or {}}
        (records_dir / f"{self._sanitize(batch_id)}.{self._sanitize(worker)}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=1),
            encoding="utf-8")

    def fail(self, worker: str, batch_id: str, reason: str) -> None:
        records_dir = self.results_dir / "records"
        records_dir.mkdir(parents=True, exist_ok=True)
        (records_dir / f"{self._sanitize(batch_id)}.{self._sanitize(worker)}.failed.json").write_text(
            json.dumps({"batch_id": batch_id, "worker": worker,
                        "failed": reason}, ensure_ascii=False),
            encoding="utf-8")
        self.release(batch_id, worker=worker)

    def release(self, batch_id: str, worker: str | None = None,
                max_attempts: int = 3) -> None:
        """Drop the claim token so the batch becomes claimable again; a
        crashed or failing worker must never strand its batch. The token
        records its owner — a release by another worker is refused — and
        attempt markers bound poison-batch loops."""
        token = self.claims_dir / self._sanitize(batch_id)
        if worker is not None and token.is_dir():
            owner = (token / "owner")
            if owner.is_file() and owner.read_text(
                    encoding="utf-8").strip() != worker:
                raise ValueError(
                    f"batch {batch_id} is claimed by another worker")
        attempts_file = self.run_dir / "attempts" / f"{self._sanitize(batch_id)}.json"
        attempts_file.parent.mkdir(parents=True, exist_ok=True)
        attempts = 1
        if attempts_file.is_file():
            try:
                attempts = json.loads(
                    attempts_file.read_text(encoding="utf-8")) + 1
            except ValueError:
                attempts = 1
        attempts_file.write_text(json.dumps(attempts), encoding="utf-8")
        if token.is_dir():
            if attempts > max_attempts:
                raise ValueError(
                    f"batch {batch_id} exceeded {max_attempts} attempts")
            token.rmdir()

    def unclaimed(self) -> list[dict[str, Any]]:
        claimed = {p.name for p in self.claims_dir.iterdir() if p.is_dir()}
        return [b for b in self.batches if b["batch_id"] not in claimed]


def merge_decision_files(results_dir: str | Path) -> dict[str, Any]:
    merged: dict[int, dict] = {}
    conflicts: list[dict] = []
    for path in sorted(Path(results_dir).glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for decision in payload.get("decisions", []):
            page = int(decision["page"])
            prior = merged.get(page)
            if prior is None:
                merged[page] = decision
            elif prior != decision:
                conflicts.append({"page": page, "a": prior, "b": decision})
    return {"decisions": merged, "conflicts": conflicts,
            "pages": sorted(merged)}


def verification_sample(pages: list[int], fraction: float = 0.1,
                        seed: int = 7) -> list[int]:
    count = max(1, int(len(pages) * fraction))
    rng = random.Random(seed)
    return sorted(rng.sample(pages, min(count, len(pages))))
