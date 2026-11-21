"""Multi-evidence cross-validation: coverage, consistency, cross-check.

Every answer from a model or agent is a candidate, never a verdict.
Verification comes from independent signals:

  L1  seq_id continuity: printed SEQ IDs should be sequential; gaps are
      missed rows
  L2  dual-source consistency: OCSR SMILES vs notation-derived SMILES
      compared by InChIKey via the deployment chemistry API
  L3  mass arbitration: assembled mass vs declared mass, dual convention
  L4  cross-agent agreement: two independent reads of the same page
  L5  coverage: expected vs actual row and page counts
"""
from __future__ import annotations

import re
from typing import Any

import httpx

from .config import harness_url

_SEQ_RE = re.compile(r"SEQ ID NO[:.]?\s*(\d+)", re.IGNORECASE)


def seq_id_coverage(found: list[int | str]) -> dict[str, Any]:
    ids = sorted(int(s) for s in found if str(s).isdigit())
    if not ids:
        return {"coverage": [], "gaps": [], "expected": 0, "found": 0}
    lo, hi = ids[0], ids[-1]
    expected = set(range(lo, hi + 1))
    found_set = set(ids)
    gaps = sorted(expected - found_set)
    return {"coverage": sorted(found_set), "gaps": gaps,
            "expected": len(expected), "found": len(ids)}


def dual_source_consistency(notation_smiles: str, ocsr_smiles: str
                            ) -> dict[str, Any]:
    """Compare notation-derived SMILES with OCSR-derived SMILES by
    InChIKey via the deployment chemistry API."""
    if not notation_smiles or not ocsr_smiles:
        return {"verdict": "incomplete", "reason": "missing smiles"}
    try:
        key_a = httpx.post(
            f"{harness_url().rstrip('/')}/v1/harness/inchikey",
            json={"smiles": notation_smiles}, timeout=30.0).json().get("inchikey")
        key_b = httpx.post(
            f"{harness_url().rstrip('/')}/v1/harness/inchikey",
            json={"smiles": ocsr_smiles}, timeout=30.0).json().get("inchikey")
    except httpx.HTTPError:
        return {"verdict": "incomplete", "reason": "deployment unreachable"}
    if not key_a or not key_b:
        return {"verdict": "incomplete", "reason": "invalid smiles"}
    if key_a == key_b:
        return {"verdict": "consistent", "inchikey": key_a}
    return {"verdict": "disagreed", "inchikey_a": key_a,
            "inchikey_b": key_b}


def completeness_check(found: list[dict], total_pages: int,
                       pages_with_data: int,
                       id_key: str = "seq_id") -> dict[str, Any]:
    found_ids = set()
    for row in found:
        match = _SEQ_RE.search(str(row.get(id_key) or row.get("notation") or ""))
        if match:
            found_ids.add(int(match.group(1)))
    return {"found_rows": len(found), "pages_with_data": pages_with_data,
            "total_pages": total_pages,
            "data_ratio": round(pages_with_data / max(total_pages, 1), 2),
            "unique_ids": len(found_ids)}


def cross_check(readings: list[dict[str, Any]], key_fields: list[str]
                ) -> dict[str, Any]:
    if len(readings) < 2:
        return {"verdict": "single_source", "agreement": True}
    ref = readings[0]
    for other in readings[1:]:
        for field in key_fields:
            if str(ref.get(field, "")) != str(other.get(field, "")):
                return {"verdict": "disagreed", "field": field,
                        "a": ref.get(field), "b": other.get(field)}
    return {"verdict": "consistent"}
