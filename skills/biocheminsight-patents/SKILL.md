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

Use BioChemInsight for document processing, structure recognition, assembly and deterministic validation. Use the calling model to read evidence and resolve context through the agent-perception workflow. Select tools by their advertised capabilities and contracts. Deployment internals can change independently of the workflow.

Retain source pages, printed IDs, units, and the distinction between a complete molecule and its assembly evidence. Retry an unreadable region with a tighter crop or higher resolution once, then report the specific uncertainty. Require row-owned attachment evidence and a validated complete graph before treating an assembled candidate as a molecule.

## Directory analysis

Run `biocheminsight-stats --dashboard` from the directory where the user is working. Use `--sort` to rank tasks by a measure, `--match` to narrow the scope and `--limit` to shorten the visible list. Use `--json` for further analysis. When calling `local_task_stats` through MCP, pass the user's directory explicitly if the server has a different working directory.

The inventory reads local task records, result tables and exports recursively. Compare complete molecule rows, assemblies, review flags, unresolved rows and assay counts. A compound ID is counted once per task, while an assay count represents exported rows. Check scan errors and missing tables before interpreting counts. Identify duplicate exports before aggregating independent runs.
