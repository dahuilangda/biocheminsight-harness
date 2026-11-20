# L3 — SAR analysis with the peptide evidence ladder

Full structure-activity analysis: peptide rows verified through the
deterministic evidence ladder, assay values joined on compound identity,
every gap named. Assumes L2 produced `detected_pages`, selected assay pages
and their OCR markdown.

## The evidence ladder (in call order)

1. `parse_peptide_notation(notation)` — tokens, terminal markers, linear vs
   cyclo. A printed grammar never spaces inside a token; a space between
   alphanumeric fragments is a lost dash and rejoins as one.
2. `resolve_peptide_notation(notation, declared_mass, form, seq_id)` —
   candidates per token run the ladder: document memory → lexicon → builtin
   monomer dictionary → name lookups → OCSR crops. Every candidate combo is
   assembled and the dual-convention mass arbitration decides.
3. Report the verdict exactly: `ok`, `delta`, `mass_convention`,
   `unknown` tokens, `gaps`.

## Verdict semantics

- `ok: true, delta ≈ 0` — accepted; cite the SMILES and page.
- `unknown: [...]` — real findings. Report them with their page. Never
  guess a residue code from a garbled OCR reading.
- `ok: false, gaps: [no candidate combination passed arbitration]` — the
  assembled molecule failed the mass contract. Report the delta and move on.
- `deferred: true` — dimer rows; deferred to the dimer assembly stage.

The mass arbitration never accepts a wrong reading: a garbled notation can
only fail a row, never silently pass one.

## Measurement session (value extraction with the agent as the model)

For assay pages whose values the deployment should extract without
configured model keys, drive the review session:

1. `measurement_review_start(source_markdown, out_dir)` — returns the
   extract prompt file.
2. Answer it as the model would (the observation JSON per
   `references/report-format.md` contracts); write the raw answer to a
   file.
3. `measurement_review_submit(session_id, answer_file, out_dir)` — returns
   the next prompt (review, revise, final review) until `done: true` with
   the review result.

The deployment validates every answer against the measurement contract;
your answers are model-style text, the deterministic checks stay neutral.

## SAR join

1. Group verified rows by `seq_id`; a compound may carry both a potency
   value and a verified SMILES.
2. Join assay rows on compound id (never on row order or formula).
3. Build the activity table: compound id | sequence | SMILES | endpoint |
   value | unit | page.

## Report contract

See `references/report-format.md`. Minimum sections: structures with SMILES
and pages, assay rows with endpoints and units, verified peptide verdicts
with mass deltas and conventions, the named-gap list, and a coverage line
(verified / total, pages covered / total).

## Reading discipline

- One perception retry at higher resolution per unreadable page; then the
  gap list.
- Stereochemistry markers (`[C@H]`, `[C@@H]`, `/`, `\`) are copied
  verbatim from readings; they are not normalized by you.
- Report potencies with their units and assay context (which endpoint, which
  cell line) — a number without its endpoint is not a finding.
