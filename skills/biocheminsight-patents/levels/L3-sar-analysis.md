# SAR analysis

## Structure and identity verification

Reconcile the source identifier, graph, and measurement context. Link assays through verified compound identity, preserving the original label. Keep repeated or conflicting IDs unresolved until page and row evidence disambiguates them. Use `verify_extraction` for independent readings and `verify_dual_source` for independent graph readings.

For Markush assembly, trace the scaffold and each substituent to its own page and source region. Follow the table across pages and check that the row identifier and variable label still apply. Compare both ends of each attachment and the bond order with the source. Check the assembled graph for unresolved sites, changed stereochemistry and undeclared atoms. Use an independently stated full structure or name when present. Report conflicting or unreadable evidence as a gap and keep it out of verified joins.

For supported peptide notation, use `parse_peptide_notation` and `resolve_peptide_notation`. Supply only reported mass evidence, using `ion_mz` and `ion_charge` together when stated as an ion measurement. Record the tool verdict, mass convention, delta, and unresolved tokens. Treat mass agreement as a consistency check. Preserve the source's stereochemistry and terminal markers.

## Measurements

Use `measurement_review_start` and `measurement_review_submit` for agent-driven review. Store answers outside the reserved prompt filename pattern `review_<id>_*.txt`. Follow the returned prompts and inspect the final result once the session reports completion.

Join verified structures and measurements on compound identity. Carry endpoint, unit, assay context, and source page through the join. Use the [report contract](../references/report-format.md) and quantify verified coverage against the scoped rows and pages.
