# Agent perception

Use [page taxonomy](../references/page-taxonomy.md) to choose source pages. A page may support several extraction stages. Read manageable sheets with `render_pages`. Record page-level structure and measurement decisions with `record_structure_detection` and `record_measurement_discovery`.

Use text extraction for selected pages and render the relevant regions when reading the layout matters. Review proposed structure boxes in page context before requesting recognition on confirmed regions. Compare the returned graph with the drawing through the available structure verification capability.

Read compound labels in page context, including labels outside the tight structure crop. In tables, preserve row and column ownership across page breaks. Check that attachment symbols are drawn within the source region before treating them as open sites. Record uncertainty where page context, OCR, and a crop disagree.
