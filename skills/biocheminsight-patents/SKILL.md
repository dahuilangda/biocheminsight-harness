---
name: biocheminsight-patents
description: Parse patent and literature compound data (structures, sequences, assays) with BioChemInsight. Use when the user asks to parse, extract or analyze WO/US/EP patent documents, journal articles, peptide notations, structure-activity data or build extraction reports.
---

# BioChemInsight patent and literature parsing

Parse compound data out of patent and literature PDFs. Two modes:

- **server mode**: a BioChemInsight deployment runs the heavy pipeline
  (layout detection, OCSR models). Use when `BIOCHEMINSIGHT_URL` is
  reachable.
- **agent mode**: you are the perception layer. The harness renders pages,
  you read them and answer structured questions; deterministic chemistry
  (notation parsing, evidence ladder, mass arbitration) runs in-process.

## Server mode (batch, one PDF end to end)

1. `upload_pdf(path)` -> pdf_id.
2. `start_full_pipeline(pdf_id)` -> task_id.
3. Poll `task_status(task_id)` until completed or failed.
4. `download_task_result(task_id, dest)`; the zip contains structures.csv,
   assay rows, merged.csv and the audit.
5. `build_extraction_report(task_dir, report.md)` and read it to the user.

## Agent mode (you are the model)

Structure page discovery:

1. `render_pages(pdf, [1..N], sheet.png)` — one contact sheet per dozen pages.
2. Look at the sheet. For every panel decide `page`, `has_structure`,
   `confidence`, `reason`. A rotated dense table with SMILES/notation cells
   counts as a structure page.
3. `record_structure_detection(out, decisions)`.

Measurement discovery:

1. `render_pages(pdf, candidates, sheet.png)` per batch.
2. Decide `page`, `has_assay_data`, `assay_names`, `confidence`, `reason`
   for each panel. Assay tables report measured values (IC50, EC50, Ki) tied
   to compound identifiers; compound-structure tables with notations are not
   assay data.
3. `record_measurement_discovery(out, decisions)`.

Assay-name reconciliation:

1. Collect the candidate assay names and the OCR'd source context
   (`ocr_pages`).
2. Decide per candidate: `merge`, `drop` or `rename`, with evidence.
3. `record_assay_reconciliation(out, decisions)`.

## Peptide rows (deterministic, no model involved)

- `parse_peptide_notation(notation)` — tokens and terminal markers.
- `resolve_peptide_notation(notation, declared_mass, form, seq_id)` — the
  evidence ladder plus dual-convention mass arbitration. Report `ok`,
  `delta`, `unknown` tokens and `gaps` verbatim; an unknown token is a
  finding, never something to guess.
- `peptide_fragment_forms(smiles)` — backbone and cap forms.
- `mass_arbitration(smiles, declared_mass)` — standalone mass check.

## Rules

- Report `gaps` and `unknown` tokens to the user verbatim. Never guess a
  residue, a name or a mass from a garbled reading.
- A failed perception step is retried once at higher resolution
  (`render_page` with a bigger dpi on the single page); a second failure is
  a finding, not something to paper over.
- Cite page numbers for every extracted row.
