# Task analytics

Use the user's current directory as the inventory root. Pass it explicitly to `local_task_stats` when the MCP server has a separate working directory.

Use `biocheminsight-stats --dashboard` for the terminal view and `--json` for further analysis. Rank by the metric relevant to the request. Filter paths with `--match` and limit the displayed rows with `--limit`. Totals cover every matching task.

Compare complete molecule rows, assembly output, evidence-only rows, unresolved rows, identity gaps and assay coverage. Count IDs within each task. Check missing result tables, read errors and duplicate exports before comparing or aggregating runs. Use annotated references and explicit denominators when reporting recall or accuracy.
