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
EVIDENCE_TYPES = {"fragment", "markush", "text_substituent"}


def _summarize(directory: str, tables: dict[str, list[dict[str, str]]]) -> dict:
    structures = tables.get(STRUCTURES, [])
    types = Counter((row.get("STRUCTURE_TYPE") or "").strip().lower() for row in structures)
    assays = next((tables[name] for name in ASSAYS if name in tables), [])
    merged = next((tables[name] for name in MERGED if name in tables), [])
    compounds = set()
    missing_ids = 0
    for row in structures:
        if (row.get("STRUCTURE_TYPE") or "").strip().lower() in EVIDENCE_TYPES:
            continue
        compound_id = (row.get("CANONICAL_COMPOUND_ID") or row.get("COMPOUND_ID")
                       or row.get("compound_id") or "").strip()
        if compound_id.lower() in {"", "none", "null", "compound"}:
            missing_ids += 1
        else:
            compounds.add(compound_id)
    return {
        "path": directory,
        "tables": sorted(tables),
        "molecule_rows": len(structures) - sum(types[kind] for kind in EVIDENCE_TYPES),
        "assembled": types["markush_assembled"],
        "evidence_rows": sum(types[kind] for kind in EVIDENCE_TYPES),
        "compound_ids": len(compounds),
        "missing_ids": missing_ids,
        "assay_rows": len(assays),
        "merged_rows": len(merged),
    }


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
        if artifacts:
            tables = {}
            for name in sorted(artifacts):
                try:
                    with (folder / name).open(encoding="utf-8-sig", newline="") as stream:
                        tables[name] = list(csv.DictReader(stream, strict=True))
                except (OSError, UnicodeError, csv.Error) as exc:
                    errors.append({"path": str(relative / name), "error": str(exc)})
            if tables:
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
    return {"root": str(root), "tasks": tasks, "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--json", action="store_true", help="emit the inventory as JSON")
    parser.add_argument("--sort", choices=("path", "molecule_rows", "assembled", "missing_ids", "assay_rows"), default="path")
    args = parser.parse_args()
    try:
        inventory = scan_tasks(args.root)
    except OSError as exc:
        parser.error(str(exc))
    tasks = inventory["tasks"]
    if args.sort != "path":
        tasks.sort(key=lambda task: -task[args.sort])
    if args.json:
        print(json.dumps(inventory, ensure_ascii=False, indent=2))
        return 0
    columns = (("molecule_rows", "Molecules"), ("assembled", "Assembled"),
               ("evidence_rows", "Evidence"), ("compound_ids", "IDs"),
               ("missing_ids", "Missing ID"), ("assay_rows", "Assays"), ("merged_rows", "Merged"))
    print(f"{len(tasks)} tasks in {inventory['root']}")
    if tasks:
        print(" ".join(f"{label:>10}" for _, label in columns), " Task")
        for task in tasks:
            path = "".join(char if char.isprintable() else "?" for char in task["path"])
            print(" ".join(f"{task[key]:>10}" for key, _ in columns), "", path)
        totals = {key: sum(task[key] for task in tasks) for key, _ in columns}
        print(" ".join(f"{totals[key]:>10}" for key, _ in columns), " Total")
    for error in inventory["errors"]:
        print(f"{error['path']!r}: {error['error']!r}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
