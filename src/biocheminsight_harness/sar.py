"""SAR table: join verified notation rows with assay measurements.

The join key is the printed sequence identifier (SEQ ID NO:N). Structure
rows from the notation ladder carry verified SMILES and mass; assay rows
from the measurement review carry endpoint, value and unit. A compound
appears in the SAR table only when both sides agree on the identifier —
a row missing from either side lands in the named-gap list."""
from __future__ import annotations

import re
from typing import Any

_SEQ_RE = re.compile(r"SEQ ID NO[:.]?\s*(\d+)", re.IGNORECASE)


def _seq_id(text: str) -> int | None:
    match = _SEQ_RE.search(text or "")
    return int(match.group(1)) if match else None


def build_sar_table(structures: list[dict[str, Any]],
                    measurements: list[dict[str, Any]]) -> dict[str, Any]:
    """Join verified notation rows with assay observations on seq_id.

    structures: rows with seq_id, notation, smiles, mass, verdict, page
    measurements: observations with seq_id or compound text, endpoint,
                  value, unit
    Returns {sar_rows, structure_only, assay_only, conflicts}."""
    struct_by_seq: dict[int, dict] = {}
    assay_by_seq: dict[int, list[dict]] = {}
    structure_only: list[dict] = []
    assay_only: list[dict] = []

    for row in structures:
        seq = row.get("seq_id")
        if seq is None:
            seq = _seq_id(row.get("notation") or row.get("notation_text") or "")
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
            "assay_only": assay_only,
            "joined": len(sar_rows)}


def sar_summary(sar_rows: list[dict]) -> list[str]:
    """Narrative SAR observations from the joined table."""
    lines = []
    by_endpoint: dict[str, list[dict]] = {}
    for row in sar_rows:
        by_endpoint.setdefault(row.get("endpoint", ""), []).append(row)

    for endpoint, rows in sorted(by_endpoint.items()):
        values = []
        for row in rows:
            try:
                values.append((float(row["value"]), row))
            except (ValueError, KeyError):
                pass
        if len(values) < 2:
            continue
        values.sort()
        best = values[0]
        worst = values[-1]
        lines.append(f"{endpoint}: {len(rows)} compounds, "
                     f"best {best[1].get('notation', '')[:40]} "
                     f"({best[0]:.4g}), "
                     f"worst {worst[1].get('notation', '')[:40]} "
                     f"({worst[0]:.4g})")
    return lines
