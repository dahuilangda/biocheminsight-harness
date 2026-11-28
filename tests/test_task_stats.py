import json
from zipfile import ZipFile

from biocheminsight_harness import task_stats


def test_scan_counts_molecules_and_evidence_separately(tmp_path):
    task = tmp_path / "run"
    task.mkdir()
    (task / "structures.csv").write_text(
        "COMPOUND_ID,SMILES,STRUCTURE_TYPE,LOCAL_EVIDENCE_STATUS,RESULT_ONLY,FILTERED_OUT\n"
        "A,CCO,markush_assembled,needs_review,,\n"
        "A,CCN,complete_compound,,,\n"
        ",CC,complete_compound,,,\n"
        "B,*CC,fragment,,,\n"
        "C,,complete_compound,,,\n"
        "D,CCO,complete_compound,,,true\n"
        "E,,,,true,\n",
        encoding="utf-8",
    )
    (task / "assays.csv").write_text("COMPOUND_ID,VALUE\nA,4\nA,7\n", encoding="utf-8")
    with ZipFile(task / "run_results.zip", "w") as bundle:
        bundle.write(task / "structures.csv", "structures.csv")
    with ZipFile(tmp_path / "other.zip", "w") as bundle:
        bundle.writestr("results/merged.csv", "COMPOUND_ID,VALUE\nA,4\n")
    (tmp_path / "damaged.zip").write_bytes(b"invalid")
    unfinished = tmp_path / "unfinished"
    unfinished.mkdir()
    (unfinished / "task_queue.jsonl").write_text("", encoding="utf-8")

    inventory = task_stats.scan_tasks(tmp_path)
    assert [row["path"] for row in inventory["tasks"]] == ["other.zip!/results", "run", "unfinished"]
    assert inventory["tasks"][-1]["tables"] == []
    assert inventory["totals"] == {
        "molecule_rows": 3, "assembled": 1, "evidence_rows": 1, "unresolved_rows": 2,
        "result_only_rows": 1, "review_rows": 1, "compound_ids": 1, "missing_ids": 1,
        "assay_rows": 2, "merged_rows": 1,
    }
    assert [error["path"] for error in inventory["errors"]] == ["damaged.zip"]


def test_dashboard_limits_rows_without_changing_totals(tmp_path, monkeypatch, capsys):
    for name, count in [("series-a", 3), ("series-b", 1), ("other", 5)]:
        folder = tmp_path / name
        folder.mkdir()
        (folder / "assays.csv").write_text("COMPOUND_ID,VALUE\n" + "A,4\n" * count)
    monkeypatch.chdir(tmp_path)
    arguments = ["biocheminsight-stats", "--sort", "assay_rows", "--match", "series", "--limit", "1"]
    monkeypatch.setattr("sys.argv", [*arguments, "--dashboard"])
    assert task_stats.main() == 0
    dashboard = capsys.readouterr().out
    assert "2 tasks" in dashboard and "Assays 4" in dashboard
    assert "series-a" in dashboard and "series-b" not in dashboard and "other" not in dashboard

    monkeypatch.setattr("sys.argv", [*arguments, "--json"])
    assert task_stats.main() == 0
    inventory = json.loads(capsys.readouterr().out)
    assert inventory["task_count"] == 2
    assert inventory["totals"]["assay_rows"] == 4
    assert [task["path"] for task in inventory["tasks"]] == ["series-a"]
