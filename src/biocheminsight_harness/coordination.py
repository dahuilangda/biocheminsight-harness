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
    """Batch manifest plus atomic claims and results under a run dir."""

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
                    "status": "pending",
                })
            manifest.write_text(
                json.dumps(batches, ensure_ascii=False, indent=1),
                encoding="utf-8")
        return cls(run_dir)

    def claim(self, worker: str, count: int = 1) -> list[dict[str, Any]]:
        claimed: list[dict[str, Any]] = []
        for batch in self.batches:
            if len(claimed) >= count:
                break
            if batch["status"] != "pending":
                continue
            token = self.claims_dir / batch["batch_id"]
            try:
                token.mkdir()
            except FileExistsError:
                continue
            batch["status"] = "claimed"
            batch["worker"] = worker
            claimed.append(batch)
        if claimed:
            self._record_claims(worker, claimed)
        return claimed

    def _record_claims(self, worker: str, claimed: list[dict]) -> None:
        path = self.claims_dir / f"{worker}.json"
        prior: list[str] = []
        if path.is_file():
            prior = json.loads(path.read_text(encoding="utf-8"))
        prior.extend(batch["batch_id"] for batch in claimed)
        path.write_text(json.dumps(prior), encoding="utf-8")

    def complete(self, worker: str, batch_id: str, result_path: str | Path,
                 stats: dict[str, Any] | None = None) -> None:
        record = {"batch_id": batch_id, "worker": worker,
                  "result": Path(result_path).name, "stats": stats or {}}
        (self.results_dir / f"{batch_id}.{worker}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=1),
            encoding="utf-8")

    def fail(self, worker: str, batch_id: str, reason: str) -> None:
        (self.results_dir / f"{batch_id}.{worker}.failed.json").write_text(
            json.dumps({"batch_id": batch_id, "worker": worker,
                        "failed": reason}, ensure_ascii=False),
            encoding="utf-8")

    def unclaimed(self) -> list[dict[str, Any]]:
        claimed_tokens = {
            path.name.rsplit(".", 1)[0] for path in self.claims_dir.iterdir()
        }
        return [batch for batch in self.batches
                if batch["status"] == "pending"
                and batch["batch_id"] not in claimed_tokens]


def merge_decision_files(results_dir: str | Path) -> dict[str, Any]:
    """Union per-batch decision files; conflicting pages are surfaced."""
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
    """Deterministic sample for dual-read cross-checking."""
    count = max(1, int(len(pages) * fraction))
    rng = random.Random(seed)
    return sorted(rng.sample(pages, min(count, len(pages))))
