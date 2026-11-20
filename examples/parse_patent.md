# Example: parse a patent end to end

User request:

> 帮我解析 WO2025137159 这篇专利，输出结构、序列、活性数据，最后给一份报告

## Server mode

1. `upload_pdf("/data/WO2025137159A1.pdf")` → `pdf_id`
2. `start_full_pipeline(pdf_id)` → `task_id`
3. Poll `task_status(task_id)`; the run covers page detection, structure
   extraction (MolDetv2 + OCSR), measurement discovery and the merged CSV.
4. `download_task_result(task_id, "out/")` → zip with `structures.csv`,
   `assays.csv`, `merged.csv`, audit trail.
5. `build_extraction_report("out/", "report.md", "WO2025137159 SAR")`.
6. Read `report.md` and summarize the findings for the user.

## Agent mode

You are the perception layer; the deployment only runs the deterministic
chemistry.

1. Structure page discovery, a contact sheet per dozen pages:

   ```
   render_pages(pdf, [1..12], "sheets/01.png")
   ```

   Read the sheet. A rotated dense table with SMILES/notation cells is a
   structure page. Answer for every panel, then validate and store:

   ```
   record_structure_detection("out/detect_01.json", [
     {"page": 58, "has_structure": true,  "confidence": "high",
      "reason": "dense compound table with notation cells"},
     {"page": 12, "has_structure": false, "confidence": "high",
      "reason": "prose"},
   ])
   ```

2. Measurement discovery, same pattern with `has_assay_data`,
   `assay_names`, `reason` per panel, then
   `record_measurement_discovery`.

3. OCR the selected assay pages through the VL-1.6 service:

   ```
   ocr_pages(pdf, selected_pages, "out/assay_pages.json")
   ```

4. Assay-name reconciliation: decide `merge`, `drop` or `rename` per
   candidate with evidence, then `record_assay_reconciliation`.

5. Peptide rows run deterministically — no model involved:

   ```
   resolve_peptide_notation(
     "ac-I-H-Ogl-T-I-P-A-D-O3S-W-D-W-O3S-K-dR-am (SEQ ID NO:163)",
     declared_mass=1970.355, form="M", seq_id="163")
   ```

   Report `ok`, `delta` and any `unknown` tokens verbatim. An unknown
   token is a finding.

## Report

Assemble `report.md` with: structure counts and SMILES, assay rows with
page citations, peptide verdicts with mass deltas, and every named gap.
Never fold a gap into a result.
