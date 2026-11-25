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
3. Poll `task_status(task_id)` every ~30 s and keep polling: a request
   waits as long as you ask and goes on the moment it is answered. The
   stages in order: structure page detection → assay page discovery →
   structure extraction → result tables → merge.
4. Whenever `task_status` reports requests pending, take the next batch
   with `perception_batch(task_id)`: every request is a text block (id,
   task name, prompt, any earlier answer of yours that was rejected)
   followed by its sheet image when it has one; a request without an
   image is a text question and its prompt is the whole request. Answer
   only from what the image or the text shows, then submit the batch
   with `perception_answers(task_id, <JSON list of {request_id, answer}>)`.
   A sheet that shows several numbered images is answered with one
   object keyed by the number, `{"1": {...}, "2": {...}}`.
   Call again until nothing is pending and the status is `completed`.
   Never take more than one batch at a time: each sheet is an image your
   context must carry. On a long backlog, answer per batch from a fresh
   subagent context so the coordinating session accumulates no sheets.
5. On `completed`: `download_task_result(task_id, "out/")` → zip with
   `structures.csv`, `bioactivity.csv`, `merged_results.csv`, audit trail.
6. `build_extraction_report("out/", "report.md", title)`; read `report.md`
   and present the findings.

## Exit criteria

- `report.md` exists with structure, assay and merged counts.
- Any `failed` task status is reported with its `error` verbatim; do not
  retry more than once before telling the user.

## Notes

- Every model call of the run, with an image or text only, is a request
  for you (declared per task); the deployment needs no model keys.
- If the deployment is unreachable, switch to L2 (agent perception mode).
