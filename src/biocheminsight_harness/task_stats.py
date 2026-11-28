"""Inventory local extraction results and render a terminal summary."""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
from collections import Counter
from pathlib import Path
from zipfile import BadZipFile, ZipFile

STRUCTURES = "structures.csv"
ASSAYS = ("bioactivity.csv", "assays.csv")
MERGED = ("merged_results.csv", "merged.csv")
ARTIFACTS = {STRUCTURES, *ASSAYS, *MERGED}
TASK_MARKERS = {"task_queue.jsonl", "task_steps.jsonl"}
EVIDENCE_TYPES = {"fragment", "markush", "text_substituent", "scaffold", "attachment_fragment", "raw_fragment"}
TRUE_VALUES = {"true", "1", "yes"}
MISSING_IDS = {"", "none", "null", "nan", "compound"}
METRICS = {
    "molecule_rows": "Molecules",
    "assembled": "Assembled",
    "evidence_rows": "Evidence",
    "unresolved_rows": "Unresolved",
    "result_only_rows": "Result only",
    "review_rows": "Review",
    "compound_ids": "IDs",
    "missing_ids": "Missing ID",
    "assay_rows": "Assays",
    "merged_rows": "Merged",
}
TABLE_METRICS = ("molecule_rows", "assembled", "evidence_rows", "compound_ids", "missing_ids", "assay_rows", "merged_rows")


def _summarize(directory: str, tables: dict[str, list[dict[str, str]]]) -> dict:
    structures = tables.get(STRUCTURES, [])
    assays = next((tables[name] for name in ASSAYS if name in tables), [])
    merged = next((tables[name] for name in MERGED if name in tables), [])
    compounds = set()
    counts: Counter[str] = Counter()
    for row in structures:
        kind = (row.get("STRUCTURE_TYPE") or "").strip().lower()
        if (row.get("RESULT_ONLY") or "").strip().lower() in TRUE_VALUES:
            counts["result_only_rows"] += 1
            continue
        if kind in EVIDENCE_TYPES:
            counts["evidence_rows"] += 1
            continue
        smiles = (row.get("SMILES") or row.get("smiles") or "").strip()
        filtered = (row.get("FILTERED_OUT") or "").strip().lower() in TRUE_VALUES
        if not smiles or "*" in smiles or filtered:
            counts["unresolved_rows"] += 1
            continue
        counts["molecule_rows"] += 1
        if kind == "markush_assembled":
            counts["assembled"] += 1
        if (row.get("LOCAL_EVIDENCE_STATUS") or "").strip().lower() in {"needs_review", "failed"}:
            counts["review_rows"] += 1
        compound_id = (row.get("CANONICAL_COMPOUND_ID") or row.get("COMPOUND_ID")
                       or row.get("compound_id") or "").strip()
        if compound_id.lower() in MISSING_IDS:
            counts["missing_ids"] += 1
        else:
            compounds.add(compound_id)
    counts.update(compound_ids=len(compounds), assay_rows=len(assays), merged_rows=len(merged))
    return {"path": directory, "tables": sorted(tables), **{key: counts[key] for key in METRICS}}


def _totals(tasks: list[dict]) -> dict:
    return {key: sum(task[key] for task in tasks) for key in METRICS}


def scan_tasks(root: str | Path = ".") -> dict:
    root = Path(root).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise NotADirectoryError(root)
    tasks = []
    errors = []

    def read_error(exc: OSError) -> None:
        errors.append({"path": str(exc.filename or root), "error": str(exc)})

    for directory, subdirs, filenames in os.walk(root, onerror=read_error):
        subdirs[:] = sorted(name for name in subdirs if not name.startswith("."))
        folder = Path(directory)
        relative = folder.relative_to(root)
        artifacts = ARTIFACTS.intersection(filenames)
        if artifacts or TASK_MARKERS.intersection(filenames):
            tables = {}
            for name in sorted(artifacts):
                try:
                    with (folder / name).open(encoding="utf-8-sig", newline="") as stream:
                        tables[name] = list(csv.DictReader(stream, strict=True))
                except (OSError, UnicodeError, csv.Error) as exc:
                    errors.append({"path": str(relative / name), "error": str(exc)})
            tasks.append(_summarize(str(relative), tables))
        for filename in sorted(filenames):
            archive = folder / filename
            if archive.suffix.lower() != ".zip":
                continue
            if artifacts and archive.stem == f"{folder.name}_results":
                continue
            try:
                with ZipFile(archive) as bundle:
                    groups: dict[Path, dict[str, str]] = {}
                    for item in bundle.infolist():
                        path = Path(item.filename)
                        if path.name in ARTIFACTS and "audit" not in path.parts[:-1]:
                            groups.setdefault(path.parent, {})[path.name] = item.filename
                    if not groups and any(Path(name).name in TASK_MARKERS for name in bundle.namelist()):
                        groups[Path(".")] = {}
                    for prefix, paths in groups.items():
                        tables = {}
                        for name, path in paths.items():
                            with bundle.open(path) as binary, io.TextIOWrapper(binary, encoding="utf-8-sig", newline="") as stream:
                                tables[name] = list(csv.DictReader(stream, strict=True))
                        location = str(relative / filename)
                        if prefix != Path("."):
                            location += f"!/{prefix}"
                        tasks.append(_summarize(location, tables))
            except (BadZipFile, OSError, UnicodeError, csv.Error, RuntimeError, NotImplementedError) as exc:
                errors.append({"path": str(relative / filename), "error": str(exc)})
    tasks.sort(key=lambda task: task["path"])
    return {"root": str(root), "tasks": tasks, "totals": _totals(tasks), "errors": errors}


def _display_path(path: str) -> str:
    return "".join(char if char.isprintable() else "?" for char in path)


def _table(tasks: list[dict], totals: dict) -> None:
    columns = [(key, METRICS[key]) for key in TABLE_METRICS]
    print(" ".join(f"{label:>10}" for _, label in columns), " Task")
    for task in tasks:
        print(" ".join(f"{task[key]:>10}" for key, _ in columns), "", _display_path(task["path"]))
    print(" ".join(f"{totals[key]:>10}" for key, _ in columns), " Total")


def _dashboard(tasks: list[dict], totals: dict, metric: str, without_tables: int, error_count: int) -> None:
    for keys in (
        ("molecule_rows", "assembled", "evidence_rows", "unresolved_rows", "result_only_rows"),
        ("review_rows", "compound_ids", "missing_ids", "assay_rows", "merged_rows"),
    ):
        print("  ".join(f"{METRICS[key]} {totals[key]:,}" for key in keys))
    print(f"No result tables {without_tables}  Read errors {error_count}")
    if not tasks:
        return
    print()
    print(f"{METRICS[metric]} by task")
    maximum = max(task[metric] for task in tasks) or 1
    for task in tasks:
        value = task[metric]
        width = max(1, round(24 * value / maximum)) if value else 0
        bar = "#" * width
        print(f"{value:>8,}  {bar:<24}  {_display_path(task['path'])}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--json", action="store_true", help="emit the inventory as JSON")
    mode.add_argument("--dashboard", action="store_true", help="show totals and rank tasks with a terminal chart")
    parser.add_argument("--sort", choices=("path", *METRICS), help="rank tasks by a metric or sort by path")
    parser.add_argument("--match", default="", help="include task paths containing this text")
    parser.add_argument("--limit", type=int, help="maximum number of task rows to display")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    try:
        inventory = scan_tasks(args.root)
    except OSError as exc:
        parser.error(str(exc))
    tasks = [task for task in inventory["tasks"] if args.match.casefold() in task["path"].casefold()]
    sort = args.sort or ("molecule_rows" if args.dashboard else "path")
    if sort != "path":
        tasks.sort(key=lambda task: -task[sort])
    totals = _totals(tasks)
    without_tables = sum(not task["tables"] for task in tasks)
    display = tasks[:args.limit]
    if args.json:
        inventory.update(tasks=display, totals=totals, task_count=len(tasks), tasks_without_tables=without_tables)
        print(json.dumps(inventory, ensure_ascii=False, indent=2))
        return 0
    print(f"{len(tasks)} tasks in {inventory['root']}")
    if len(display) < len(tasks):
        print(f"Showing {len(display)} tasks. Totals cover all matching tasks.")
    if args.dashboard:
        metric = sort if sort != "path" else "molecule_rows"
        _dashboard(display, totals, metric, without_tables, len(inventory["errors"]))
    elif display:
        _table(display, totals)
    for error in inventory["errors"]:
        print(f"{error['path']!r}: {error['error']!r}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
