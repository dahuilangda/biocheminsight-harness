# Document extraction

Check deployment availability for the requested workflow. Use existing connection settings when available. Upload the source with `upload_pdf`, start with `start_full_pipeline`, and enable Markush assembly when complete molecules are required.

Poll `task_status` until terminal. When perception is pending, use `perception_batch` and submit through `perception_answers`. Read the full prompt, the supplied sheet if present, and any rejection reason. Keep numbered answers aligned with the source panels and submit the schema each request requires. Continue after each batch until the task reaches a terminal state. Report the saved task error if execution fails.

Inspect the actual result tables for the requested outcome. Check that expected assembled rows have complete graphs and source references, and investigate missing or ambiguous IDs before joining assays. Use `open_review_workspace` for review and `download_task_result` for a local snapshot. Unpack the snapshot before using `build_extraction_report`. Keep assembly blockers and unreadable evidence in the report when they affect coverage.
