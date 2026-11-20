---
name: biocheminsight-patents
description: Parse patent and literature compound data (structures, peptide sequences, structure-activity tables) with BioChemInsight. Use when the user asks to parse, extract or analyze WO/US/EP patent documents, journal articles, peptide notations, structure-activity data, potency tables or build extraction reports. Tiered: batch server mode, agent perception mode, and full SAR analysis.
---

# BioChemInsight patent and literature parsing

Parse compound data out of patent and literature PDFs. Deterministic
chemistry (notation parsing, evidence ladder, mass arbitration) runs without
any model; perception steps (deciding what a page contains) are answered by
you out of your own context — no model keys are configured anywhere.

## Choose the level

| request | level | doc |
|---|---|---|
| "解析这篇专利/文章" (one PDF, end to end, deployment available) | L1 | `levels/L1-document-parse.md` |
| "我自己来看页面/不要用配置的模型" or no deployment | L2 | `levels/L2-agent-perception.md` |
| "给我 SAR 分析/逐行验证/结构+活性+肽序列的完整报告" | L3 | `levels/L3-sar-analysis.md` |

Read only the level file you need. L2 and L3 assume L1's server setup
(`upload_pdf`, task lifecycle) unless no deployment is reachable.

## Tools by level

- **L1** — `upload_pdf`, `start_full_pipeline`, `task_status`,
  `download_task_result`, `build_extraction_report`.
- **L2** — `render_pages`, `render_page`, `ocr_pages`,
  `record_structure_detection`, `record_measurement_discovery`,
  `record_assay_reconciliation`.
- **L3** — `parse_peptide_notation`, `resolve_peptide_notation`,
  `peptide_fragment_forms`, `mass_arbitration`, plus every L2 tool and the
  report contract in `references/report-format.md`.

## Hard rules (all levels)

- A failed or unknown reading is a **named gap**: report it verbatim with
  its page. Never guess a residue token, a compound id or a value.
- Cite page numbers for every extracted row.
- Retry a perception step once at higher resolution (`render_page`, bigger
  dpi). A second failure is reported, never papered over.
