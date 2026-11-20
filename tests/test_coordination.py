"""Multi-agent coordination: atomic claims, merge, cross-check."""
import json
import threading

from biocheminsight_harness.coordination import (BatchLedger,
                                                 merge_decision_files,
                                                 verification_sample)


def test_partition_creates_deterministic_manifest(tmp_path):
    ledger = BatchLedger.partition(tmp_path, total_pages=551,
                                   pages_per_batch=12)
    assert len(ledger.batches) == 46
    assert ledger.batches[0]["pages"][0] == 1
    assert ledger.batches[-1]["pages"][-1] == 551

    again = BatchLedger.partition(tmp_path, 551, 12)
    assert again.batches == ledger.batches


def test_claims_are_atomic_under_threads(tmp_path):
    ledger = BatchLedger.partition(tmp_path, total_pages=100,
                                   pages_per_batch=12)
    claimed: list[str] = []
    lock = threading.Lock()

    def worker(name: str):
        for batch in ledger.claim(name, count=3):
            with lock:
                claimed.append(batch["batch_id"])

    threads = [threading.Thread(target=worker, args=(f"w{i}",))
               for i in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    ids = [entry.split(".")[0] for entry in claimed]
    assert len(ids) == len(set(ids))


def test_complete_and_merge_round_trip(tmp_path):
    ledger = BatchLedger.partition(tmp_path, total_pages=24,
                                   pages_per_batch=12)
    ledger.claim("w1", count=2)

    out = tmp_path / "out"
    out.mkdir()
    batches = [batch["batch_id"] for batch in ledger.batches]
    decisions_by_batch = {
        batches[0]: {"decisions": [
            {"page": 1, "has_structure": True, "confidence": "high",
             "reason": "table"}]},
        batches[1]: {"decisions": [
            {"page": 13, "has_structure": False, "confidence": "high",
             "reason": "prose"}]},
    }
    for batch_id, decisions in decisions_by_batch.items():
        path = out / f"{batch_id}.w1.json"
        path.write_text(json.dumps(decisions), encoding="utf-8")
        ledger.complete("w1", batch_id, path)

    merged = merge_decision_files(out)
    assert merged["conflicts"] == []
    assert merged["decisions"][1]["has_structure"] is True
    assert merged["decisions"][13]["has_structure"] is False


def test_verification_sample_is_deterministic():
    pages = list(range(1, 101))
    assert verification_sample(pages, 0.1) == verification_sample(pages, 0.1)
