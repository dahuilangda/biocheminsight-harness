"""Markdown report assembled from a finished pipeline run."""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_report(task_dir: str | Path, out_path: str | Path,
                 title: str = "") -> Path:
    """Write report.md summarizing structures, assays and named gaps."""
    task_dir = Path(task_dir)
    structures = _read_csv(task_dir / "structures.csv")
    assays = _read_csv(task_dir / "assays.csv")
    merged = _read_csv(task_dir / "merged.csv")
    audit = _load_json(task_dir / "audit.json")

    lines: list[str] = []
    lines.append(f"# {title or 'BioChemInsight extraction report'}")
    lines.append("")
    lines.append(f"- structures: {len(structures)} rows")
    lines.append(f"- assays: {len(assays)} rows")
    lines.append(f"- merged relationships: {len(merged)} rows")

    if merged:
        counter = Counter(row.get("status", "unknown") for row in merged)
        lines.append(f"- status: {dict(counter)}")

    lines.append("")
    lines.append("## Structures")
    lines.append("")
    if structures:
        lines.append("| id | smiles | page |")
        lines.append("|---|---|---|")
        for row in structures[:50]:
            lines.append(f"| {row.get('compound_id', '')} "
                         f"| {row.get('smiles', '')[:60]} "
                         f"| {row.get('page', '')} |")
        if len(structures) > 50:
            lines.append(f"| … | {len(structures) - 50} more | |")
    else:
        lines.append("none")

    lines.append("")
    lines.append("## Assays")
    lines.append("")
    if assays:
        lines.append("| compound | endpoint | value | unit |")
        lines.append("|---|---|---|---|")
        for row in assays[:50]:
            lines.append(f"| {row.get('compound_id', '')} "
                         f"| {row.get('endpoint', '')} "
                         f"| {row.get('value', '')} "
                         f"| {row.get('unit', '')} |")
        if len(assays) > 50:
            lines.append(f"| … | {len(assays) - 50} more | | |")
    else:
        lines.append("none")

    gaps = audit.get("gaps") if isinstance(audit, dict) else None
    chart_gaps = _load_json(task_dir / "chart_extraction_gaps.json")
    if not isinstance(chart_gaps, list):
        chart_gaps = []
    if gaps or chart_gaps:
        lines.append("")
        lines.append("## Named gaps")
        lines.append("")
        for gap in gaps[:30]:
            lines.append(f"- {str(gap)[:160]}")
        for gap in chart_gaps[:30]:
            lines.append(f"- chart page {gap.get('page', '?')} "
                         f"{gap.get('image', '')}: {gap.get('reason', '')[:120]}")
        if len(chart_gaps) > 30:
            lines.append(f"- … {len(chart_gaps) - 30} more chart gaps")

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out
