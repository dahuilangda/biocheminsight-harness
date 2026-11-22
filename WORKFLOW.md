# Agent workflow

The operating procedure for parsing one document. Every step validates
through the harness; nothing is accepted on a single reading.

## 1. Connect

```
configure_deployment(url="http://your-server:8000")
deployment_status()
```

## 2. Classify pages

Render a contact sheet, read it with your vision, and record decisions:

```
render_pages(pdf_path, pages, out_path)     # contact sheets
record_structure_detection(out_path, decisions)
```

Split long documents into batches with the coordination ledger so
parallel agents can share one run directory:

```
batch_partition(run_dir, total_pages, pages_per_batch=12)
batch_claim(run_dir, worker="agent-1")      # atomic, per-batch tokens
```

## 3. Read structures

For each detected page: `render_page` at 200 dpi, read the structure,
then let deterministic chemistry arbitrate — never accept a raw reading:

```
resolve_peptide_notation(notation, declared_mass, form, seq_id)
```

Acceptance authority is routed by data type: mass arbitration for rows
with a declared mass; dual-source agreement for massless rows — two
genuinely independent readings of the same code (a two-page
transcription match, or notation-SMILES vs structure-SMILES InChIKey
via `verify_dual_source`; never the same string twice); text-grounded
high-confidence statements for measurements. Chart-position readings
need a second source — alone they stay unverified. Rejected readings
are named gaps, not failures to hide.

## 4. Read measurements

```
record_measurement_discovery(out_path, decisions)   # which pages hold assays
record_assay_reconciliation(out_path, decisions)    # merge/drop/rename endpoints
```

For figure-only pages (charts instead of tables):

```
extract_page_images(pdf_path, pages, out_dir)       # native chart crops
```

Read each crop with your vision and transcribe printed values only —
axis ticks, data labels, legend entries. No interpolation. Cross-check
your transcription against OCR text where both exist:

```
verify_extraction(readings, key_fields=["value", "unit"])
```

## 5. Chemistry and SAR — and the demand-driven codebook

Run chemistry first. Read the coverage it returns: when quarantined
rows carry `unknown_codes`, the document defines residues the parser
does not know — harvest exactly those definitions (definition grids,
building-block tables, abbreviation legends), render at high
resolution, read each drawn structure, and feed the pairs:

```
record_monomer_dictionary(task_session_id, entries=[{"code": <printed>, "smiles": <your reading>}], output_dir=...)
```

then run chemistry again. No unknown codes means no harvest — the step
is driven by what the document needs, not by ritual. Rules: codes
verbatim as printed; SMILES from what is actually drawn (you are the
OCSR); skip what you cannot read reliably. Entries stay candidates —
mass arbitration decides. The codebook never crosses documents: each
document teaches only itself. Arbitration failures carry structured
diagnostics (per-token masses, assembled mass vs target) — use them to
pinpoint which reading is wrong before re-reading anything.

```
peptide_fragment_forms(smiles)
mass_arbitration(smiles, declared_mass)
sar_build(structures, measurements)
sar_analysis(sar_rows)
```

## 6. Report

Prefer the server pipeline for full-document runs (it runs the same
chemistry with its own orchestration):

```
upload_pdf → start_full_pipeline → task_status → download_task_result
build_extraction_report(task_dir, out_path)
```

The run declares agent perception: when `task_status` returns
`awaiting_perception`, the pending vision calls ride in the response —
read each `sheet` image with your vision, answer with
`pipeline_perception_answer`, and the task resumes on its own. Repeat
until `completed`. Answer only from what is visibly printed; an
unreadable call stays a named gap.

The report names every gap: unreadable charts, unknown tokens, rejected
readings. A finished run with named gaps is a success; a silent drop is
a bug.

## Rules

- Perception is yours. Chemistry is the server's. Never fabricate a
  value the server can compute.
- One source is never enough: OCR and vision must agree or the row is
  a gap.
- Write every decision through the record_* tools; their contracts are
  validated before anything downstream runs.
