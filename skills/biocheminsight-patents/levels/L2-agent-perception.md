# Agent perception

Use [page taxonomy](../references/page-taxonomy.md) to choose source pages. A page may support several extraction stages. Read manageable sheets with `render_pages`. Record page-level structure and measurement decisions with `record_structure_detection` and `record_measurement_discovery`.

Use `ocr_pages` on selected pages. For drawn structures, render the page, inspect proposed boxes from `detect_structures_on_page`, and use `recognize_region` on confirmed regions. Cross-check the extracted graph with the source when `verify_structure` is available.

Read compound labels in page context, including labels outside the tight structure crop. In tables, preserve row and column ownership across page breaks. Check that attachment symbols are drawn within the source region before treating them as open sites. Record uncertainty where page context, OCR, and a crop disagree.
