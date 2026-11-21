"""SAR table: join verified notation rows with assay measurements."""
from __future__ import annotations

import re
from typing import Any

_SEQ_RE = re.compile(r"SEQ ID NO[:.]?\s*(\d+)", re.IGNORECASE)
_OPERATOR_RE = re.compile(r"^[<>≤≥~=]+\s*")


def _seq_id(text: str) -> int | None:
    match = _SEQ_RE.search(text or "")
    return int(match.group(1)) if match else None


def _parse_potency(value: str) -> float | None:
    cleaned = _OPERATOR_RE.sub("", value.strip())
    try:
        return float(cleaned)
    except ValueError:
        return None


def build_sar_table(structures: list[dict[str, Any]],
                    measurements: list[dict[str, Any]]) -> dict[str, Any]:
    struct_by_seq: dict[int, dict] = {}
    assay_by_seq: dict[int, list[dict]] = {}
    structure_only: list[dict] = []
    assay_only: list[dict] = []

    for row in structures:
        seq = row.get("seq_id")
        if not seq:
            seq = _seq_id(row.get("notation") or "")
        if seq is not None:
            struct_by_seq[int(seq)] = row

    for obs in measurements:
        seq = obs.get("seq_id")
        if seq is None:
            seq = _seq_id(obs.get("source_text") or obs.get("raw") or "")
        if seq is not None:
            assay_by_seq.setdefault(int(seq), []).append(obs)
        else:
            assay_only.append(obs)

    sar_rows: list[dict] = []
    for seq, struct in struct_by_seq.items():
        assays = assay_by_seq.pop(seq, None)
        if assays:
            for assay in assays:
                sar_rows.append({
                    "seq_id": seq,
                    "notation": struct.get("notation", ""),
                    "smiles": struct.get("smiles", ""),
                    "form": struct.get("form", ""),
                    "mass": struct.get("mass"),
                    "page": struct.get("page"),
                    "endpoint": assay.get("endpoint", ""),
                    "value": assay.get("value", ""),
                    "unit": assay.get("unit", ""),
                    "assay_name": assay.get("assay_name", ""),
                    "assay_page": assay.get("page"),
                })
        else:
            structure_only.append(struct)

    for seq, assays in assay_by_seq.items():
        for assay in assays:
            assay_only.append({**assay, "seq_id": seq})

    return {"sar_rows": sar_rows, "structure_only": structure_only,
            "assay_only": assay_only, "joined": len(sar_rows)}


def sar_summary(sar_rows: list[dict]) -> list[str]:
    by_endpoint: dict[str, list[tuple[float, dict]]] = {}
    for row in sar_rows:
        potency = _parse_potency(str(row.get("value", "")))
        if potency is not None:
            by_endpoint.setdefault(row.get("endpoint", ""), []).append(
                (potency, row))

    lines = []
    for endpoint, entries in sorted(by_endpoint.items()):
        if len(entries) < 2:
            continue
        entries.sort()
        best = entries[0]
        worst = entries[-1]
        lines.append(f"{endpoint}: {len(entries)} compounds, "
                     f"best {best[1].get('notation', '')[:40]} "
                     f"({best[0]:.4g}), "
                     f"worst {worst[1].get('notation', '')[:40]} "
                     f"({worst[0]:.4g})")
    return lines
