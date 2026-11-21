# biocheminsight-harness

Parse patent and literature compound data — structures, peptide sequences,
structure-activity tables — from inside coding agents (Claude Code, Codex,
ZCode) via natural language.

The harness inverts BioChemInsight's dependency on configured model APIs:
deterministic chemistry and document IO run in-process, and the agent
supplies the perception and judgment steps out of its own context. The
deployment's model keys disappear; the coding plan's tokens take over.

## Architecture

```
┌──────────────────────────────────────────────────────┐
│ coding agent (Claude Code / Codex / ZCode)            │
│                                                       │
│  "帮我解析 your-patent 这篇专利"                     │
│                                                       │
│  perception: agent reads rendered pages               │
│  chemistry:  evidence ladder + mass arbitration (RDKit)│
│  correction: named gaps + dual-convention arbitration │
│  output:     merged.csv + report.md + named gaps      │
└──────────────────┬───────────────────────────────────┘
                   │ MCP tools              ▲ results
                   ▼                        │
┌─────────────────────────────────────────┐
│ BioChemInsight deployment               │
│  pipeline API · paddle VL-1.6 · review UI│
└─────────────────────────────────────────┘
```

## Install

```bash
pip install -e ".[mcp,dev]"
```

Point the harness at a BioChemInsight deployment (can be on another server):

```bash
export BIOCHEMINSIGHT_URL=http://your-deployment:8000
export BIOCHEMINSIGHT_HARNESS_URL=http://your-deployment:8011
export PADDLEOCR_URL=http://your-deployment:8010
```

The harness is a pure client; only the three URLs need to be reachable.

## MCP setup

### Claude Code

```json
{
  "mcpServers": {
    "biocheminsight-harness": {
      "command": "biocheminsight-harness"
    }
  }
}
```

Or drop `skills/biocheminsight-patents` into `.claude/skills/`.

### Codex / ZCode

Add the same MCP server to your agent's tool settings, or import
`skills/biocheminsight-patents/SKILL.md` as a system prompt.

## Use

Ask in natural language:

> 帮我解析 your-patent 这篇专利，输出结构、序列和活性数据，再给一份报告

The agent follows `skills/biocheminsight-patents/SKILL.md`:

- **L1 server mode** — uploads the PDF, runs the deployment pipeline,
  downloads the merged bundle, writes a report.
- **L2 agent perception** — renders pages onto contact sheets, reads them
  itself, records per-page decisions, OCRs the selected pages.
- **L3 SAR analysis** — joins verified notation rows with assay values,
  runs the deterministic evidence ladder, reports potency patterns and
  named gaps.

## Tools

| tool | purpose |
|---|---|
| `parse_peptide_notation` | notation to tokens |
| `resolve_peptide_notation` | evidence ladder + mass arbitration |
| `peptide_fragment_forms` | backbone / cap contract forms |
| `mass_arbitration` | dual-convention mass check |
| `render_pages` / `render_page` | contact sheets and single pages |
| `record_structure_detection` | validated page decisions |
| `record_measurement_discovery` | selected assay pages and names |
| `record_assay_reconciliation` | assay-name merge/drop/rename |
| `ocr_pages` | paddle VL-1.6 markdown |
| `upload_pdf` / `start_full_pipeline` / `task_status` / `download_task_result` | server pipeline |
| `build_extraction_report` | markdown report |
| `batch_partition` / `batch_claim` / `batch_complete` / `batch_merge` | parallel coordination |
| `sar_build` / `sar_analysis` | SAR table and potency summary |

## Integration with BioChemInsight

The harness connects to three services on a BioChemInsight deployment:

| service | default URL | purpose |
|---|---|---|
| pipeline API | `:8000` | upload, task lifecycle, merged results |
| chemistry harness | `:8011` | deterministic chemistry endpoints |
| paddle VL-1.6 | `:8010` | page OCR (chunked, cancel-aware) |

Results flow back through the pipeline API: the harness downloads the
merged bundle, which the BioChemInsight review workspace already renders.
No frontend changes are needed.

For agent-mode runs, the harness renders pages locally (pdftoppm) and the
agent reads them; the paddle service is used only for chunked OCR when
text-level accuracy matters more than vision speed.

## Design notes

- Perception is supplied by the agent, validated by pydantic contracts in
  `decisions.py`; nothing the agent answers is trusted without passing its
  schema.
- Deterministic chemistry fails with named gaps: an unknown residue token
  or a mass mismatch is reported, never guessed.
- The paddle client submits pages in timeout-sized chunks and cancels
  abandoned server jobs, so a slow page cannot clog the serial worker.
- Structure pages are excluded from assay page discovery; the two stages
  share their findings through the `exclude_pages` parameter.
- Detection results are cached per document: identical re-runs skip the
  vision batches entirely.
