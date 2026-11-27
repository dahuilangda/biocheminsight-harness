---
name: biocheminsight-patents
description: Use BioChemInsight to extract and verify structures, compound identities, and measurements from patents and literature, review SAR results, or analyze extraction tasks stored in the user's current directory.
---

# BioChemInsight

Choose the workflow by the requested outcome.

- End-to-end PDF extraction with a reachable deployment. Read [document extraction](levels/L1-document-parse.md).
- Page or region inspection, or extraction with individually available tools. Read [agent perception](levels/L2-agent-perception.md).
- Identity reconciliation, structural verification, or SAR. Read [SAR analysis](levels/L3-sar-analysis.md).
- Inventory or compare local extraction tasks. Use the directory workflow below without starting a pipeline.

Use the available deployment tools for detection, OCR, structure recognition, assembly, and validation. For agent-perception tasks, answer each request from its supplied evidence and follow its response schema.

Retain source pages, printed IDs, units, and the distinction between a complete molecule and its assembly evidence. Retry an unreadable region with a tighter crop or higher resolution once, then report the specific uncertainty. Require row-owned attachment evidence and a validated complete graph before treating an assembled candidate as a molecule.

## Directory analysis

Run `biocheminsight-stats` from the user's working directory. Pass the directory explicitly to `local_task_stats(root)` when the tool server has a different working directory. Use `--help` for sorting and `--json` for downstream analysis. The inventory reads task CSVs and ZIP exports recursively without uploading files or consulting the deployment.

Compare molecule, assembled, evidence, missing ID, assay, and merged row counts by task. Review source artifacts for discrepancies before drawing conclusions. The inventory skips cached downloads inside their own task folder. Identify other copies before aggregating independent runs. Compound ID counts are per task and assay counts count exported rows. Inspect scan errors and missing tables before interpreting a low count.
