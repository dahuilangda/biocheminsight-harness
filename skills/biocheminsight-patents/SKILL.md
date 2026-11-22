---
name: biocheminsight-patents
description: Parse patent and literature compound data (structures, peptide sequences, structure-activity tables) with BioChemInsight. Use when the user asks to parse, extract or analyze patent documents, journal articles, peptide notations, structure-activity data, potency tables or build extraction reports. Results render in the BioChemInsight review workspace. Tiered: batch server mode, agent perception mode, and full SAR analysis.
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

Read only the level file you need. Each level exposes its own tools
and contracts; L2 and L3 assume L1's server setup (`upload_pdf`, task
lifecycle) unless no deployment is reachable.

## Hard rules (all levels)

- A failed or unknown reading is a **named gap**: report it verbatim with
  its page. Never guess a residue token, a compound id or a value.
- Cite page numbers for every extracted row.
- Retry a perception step once at higher resolution (`render_page`, bigger
  dpi). A second failure is reported, never papered over.

## Frontend display

After a completed run, `open_review_workspace(task_id)` returns the
BioChemInsight review workspace URL where the user can browse and edit the
extracted rows. The workspace renders structures, assay tables and the
merged SAR view; no extra export step is needed.
