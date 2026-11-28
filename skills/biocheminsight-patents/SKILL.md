---
name: biocheminsight-patents
description: Use BioChemInsight to extract and verify structures, compound identities, and measurements from patents and literature, review SAR results, or analyze extraction tasks stored in the user's current directory.
---

# BioChemInsight

Choose the workflow by the requested outcome.

- End-to-end PDF extraction with a reachable deployment. Read [document extraction](levels/L1-document-parse.md).
- Page or region inspection, or extraction with individually available tools. Read [agent perception](levels/L2-agent-perception.md).
- Identity reconciliation, structural verification, or SAR. Read [SAR analysis](levels/L3-sar-analysis.md).
- Inventory or compare local extraction tasks. Read [task analytics](levels/L4-task-analytics.md).

Use BioChemInsight for document processing, structure recognition, assembly and deterministic validation. Use the calling model to read evidence and resolve context through the agent-perception workflow. Select tools by their advertised capabilities and contracts. Deployment internals can change independently of the workflow.

Retain source pages, printed IDs, units, and the distinction between a complete molecule and its assembly evidence. Retry an unreadable region with a tighter crop or higher resolution once, then report the specific uncertainty. Require row-owned attachment evidence and a validated complete graph before treating an assembled candidate as a molecule.
