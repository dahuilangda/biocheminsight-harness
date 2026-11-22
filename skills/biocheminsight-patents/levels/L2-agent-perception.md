# L2 — agent perception mode

You are the perception layer: the harness renders pages, you look and
answer structured questions, the harness validates and stores your answers.
No model keys are needed.

## Perception round-trip

```
render_pages(pdf, pages, sheet.png)   → one image
    you look at it                    → per-page decisions
record_*_decisions(out, decisions)    → validated, stored
```

## Stage 1 — structure page discovery

1. Batch the page range into contact sheets of ~12 pages:
   `render_pages(pdf, [1..12], "sheets/01.png")`.
2. For every panel answer: `page`, `has_structure`, `confidence`, `reason`.
   - `has_structure: true` covers drawn scaffolds **and** rotated dense
     tables whose cells carry SMILES or peptide notations.
   - Prose-only pages are false.
3. `record_structure_detection("out/detect_01.json", decisions)`.

## Stage 2 — measurement discovery

1. Batch the remaining candidate pages the same way.
2. For every panel answer: `page`, `has_assay_data`, `assay_names`,
   `confidence`, `reason`.
   - Assay tables report **measured values** (IC50, EC50, Ki, % inhibition)
     tied to compound identifiers.
   - Compound-structure tables with notations and potency columns are
     structure pages, not assay pages.
   - If a panel is unreadable: `has_assay_data: null`, `confidence: "low"`.
     Unreadable is a finding, not a guess.
3. `record_measurement_discovery("out/discovery.json", decisions)`.

## Stage 3 — source OCR for the selected pages

`ocr_pages(pdf, selected_pages, "out/assay_pages.json")` through the paddle
VL-1.6 service. Chunks are submitted in timeout-sized pieces and canceled
server-side if abandoned; you do not manage this.

## Retry rule

A page you could not read: re-render that single page with
`render_page(pdf, page, page.png, dpi=300)` and look again. A second
failure is reported as a named gap.

## Exit criteria

- `detected_pages`, `selected_pages` and `assay_names` recorded.
- Every unreadable page is in the named-gap list with its reason.


## Boxing structures

```
render_page(pdf_path, page, out_path, dpi=200)
detect_structures_on_page(out_path, include_crops=True, out_dir="crops/")
recognize_region(crop_path, x, y, w, h)
verify_structure(smiles, crop_path)
```

Read each crop to confirm the detection before recognition. Submit
decisions via `record_structure_detection`.
