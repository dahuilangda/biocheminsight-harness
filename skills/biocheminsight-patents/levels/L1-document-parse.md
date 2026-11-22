# L1 — document parse (server mode)

End-to-end parse of one PDF through a running BioChemInsight deployment.
Requires `BIOCHEMINSIGHT_URL` reachable.

## Steps

0. Configure the deployment connection (requires all three endpoints
   reachable): `configure_deployment(url, ocr_url, user, password)` then
   verify with `deployment_status()` — all three probes must be true.

1. `upload_pdf(path)` → `pdf_id`.
2. `start_full_pipeline(pdf_id, strictness="strict", assemble_markush=true)`
   → `task_id`.
3. Poll `task_status(task_id)` every ~30 s. The stages in order:
   structure page detection → assay page discovery → measurement review →
   structure extraction → merge.
4. If the status is `awaiting_perception`: the response carries a
   bounded batch of the pending requests, each with a `sheet_url`. Fetch
   that batch's sheets, read each image with your vision, and post
   answers via `pipeline_perception_answer(task_id, request_id, <JSON
   per the request's contract>)`. Then poll again — answered requests
   drop out and the next batch appears — until `completed`. Never fetch
   every pending sheet at once: each one is an image your context must
   carry. On a long backlog, answer per batch from a fresh subagent
   context so the coordinating session accumulates no sheets at all.
5. On `completed`: `download_task_result(task_id, "out/")` → zip with
   `structures.csv`, `bioactivity.csv`, `merged_results.csv`, audit trail.
6. `build_extraction_report("out/", "report.md", title)`; read `report.md`
   and present the findings.

## Exit criteria

- `report.md` exists with structure, assay and merged counts.
- Any `failed` task status is reported with its `error` verbatim; do not
  retry more than once before telling the user.

## Notes

- Vision calls route to the connected coding agent (declared per task); no keys are needed from you.
- If the deployment is unreachable, switch to L2 (agent perception mode).
