# Agent perception

Use [page taxonomy](../references/page-taxonomy.md) to choose source pages. A page may support several extraction stages. Read manageable sheets with `render_pages`. Record page-level structure and measurement decisions with `record_structure_detection` and `record_measurement_discovery`.

Use text extraction for selected pages and render the relevant regions when reading the layout matters. Review proposed structure boxes in page context before requesting recognition on confirmed regions. Compare the returned graph with the drawing through the available structure verification capability.

For compound IDs and names, follow [compound identity evidence](../references/compound-identity.md). Check that attachment symbols are drawn within the source region before treating them as open sites. Record uncertainty where page context, OCR, and a crop disagree.

When a page contains activity or ADME results, use the [measurement evidence rules](../references/measurement-evidence.md) to read the result region.
