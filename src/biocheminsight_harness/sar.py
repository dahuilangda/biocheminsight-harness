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
        raw = row.get("seq_id")
        seq = int(raw) if raw and str(raw).isdigit() else _seq_id(row.get("notation") or "")
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


def sar_summary(sar_rows: list[dict],
                higher_is_better: dict[str, bool] | None = None) -> dict:
    """Rank per endpoint. Direction defaults to potency semantics (lower
    is better); endpoints named in higher_is_better reverse it. Cutoff
    operators travel with the value so '>10000' never ranks as 10000.
    Values that cannot parse are returned as named gaps."""
    directions = higher_is_better or {}
    by_endpoint: dict[str, list[tuple[float, dict]]] = {}
    unparseable: list[dict] = []
    for row in sar_rows:
        raw = str(row.get("value", ""))
        operator = _OPERATOR_RE.match(raw)
        potency = _parse_potency(raw)
        endpoint = row.get("endpoint", "")
        if potency is None:
            if raw.strip():
                unparseable.append({"endpoint": endpoint,
                                    "value": raw,
                                    "notation": row.get("notation", "")})
            continue
        by_endpoint.setdefault(endpoint, []).append(
            (potency, {**row, "operator": operator.group(0).strip() if operator else ""}))

    lines = []
    for endpoint, entries in sorted(by_endpoint.items()):
        if len(entries) < 2:
            continue
        reverse = directions.get(endpoint, False)
        ordered = sorted(entries, key=lambda t: t[0], reverse=reverse)
        best, worst = ordered[0], ordered[-1]
        lines.append(f"{endpoint}: {len(entries)} compounds, "
                     f"best {best[1].get('notation', '')[:40]} "
                     f"({best[1].get('value', '')}), "
                     f"worst {worst[1].get('notation', '')[:40]} "
                     f"({worst[1].get('value', '')})")
    return {"summary": lines, "unparseable_values": unparseable}
