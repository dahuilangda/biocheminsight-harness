# L1 — document parse (server mode)

End-to-end parse of one PDF through a running BioChemInsight deployment.
Requires `BIOCHEMINSIGHT_URL` reachable.

## Steps

1. `upload_pdf(path)` → `pdf_id`.
2. `start_full_pipeline(pdf_id, strictness="strict", assemble_markush=true)`
   → `task_id`.
3. Poll `task_status(task_id)` every ~30 s. The stages in order:
   structure page detection → assay page discovery → measurement review →
   structure extraction → merge.
4. On `completed`: `download_task_result(task_id, "out/")` → zip with
   `structures.csv`, `assays.csv`, `merged.csv`, audit trail.
5. `build_extraction_report("out/", "report.md", title)`; read `report.md`
   and present the findings.

## Exit criteria

- `report.md` exists with structure, assay and merged counts.
- Any `failed` task status is reported with its `error` verbatim; do not
  retry more than once before telling the user.

## Notes

- Vision calls route to the connected coding agent (declared per task); no keys are needed from you.
- If the deployment is unreachable, switch to L2 (agent perception mode).
