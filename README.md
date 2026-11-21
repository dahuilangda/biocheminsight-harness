# biocheminsight-harness

Parse patent and literature compound data — structures, peptide sequences,
structure-activity tables — from inside coding agents via natural language.

No API keys. No model configuration. The coding plan's tokens are the model.

## Install

Tell your coding agent:

> 安装 biocheminsight-harness 并连接到 http://your-server:8000

Or manually:

```bash
git clone https://github.com/dahuilangda/biocheminsight-harness.git
cd biocheminsight-harness
pip install -e ".[mcp,dev]"
export BIOCHEMINSIGHT_URL=http://your-server:8000
```

Register the MCP server:

```json
{ "mcpServers": { "biocheminsight-harness": { "command": "biocheminsight-harness" } } }
```

Then ask:

> 帮我解析 your-patent.pdf 这篇专利，输出结构、序列和活性数据，给一份报告

## How it works

```
you ──natural language──▶ coding agent
                             │
                ┌────────────┼────────────┐
                ▼            ▼            ▼
          render pages   evidence ladder  mass arbitration
          (pdftoppm)     (RDKit)          (dual convention)
                │            │            │
                ▼            ▼            ▼
          agent vision   named gaps    verified rows
```

The agent renders pages, reads them with its own vision, and feeds
structured answers to the harness. Deterministic chemistry validates every
answer: mass arbitration rejects wrong readings, named gaps surface
unknown tokens. No API keys, no model configuration — the coding plan's
tokens are the model.

## Architecture

```
┌────────────────────────────────────────────────┐
│ coding agent                                    │
│  perception: reads rendered pages               │
│  chemistry:  evidence ladder + mass arbitration │
│  output:     merged.csv + report.md + gaps      │
└─────────────────┬───────────────────────────────┘
                  │ MCP tools           ▲ results
                  ▼                     │
┌──────────────────────────────────────┐
│ BioChemInsight deployment            │
│  pipeline · paddle VL-1.6 · review UI│
└──────────────────────────────────────┘
```

## Tools

| tool | purpose |
|---|---|
| `parse_peptide_notation` | notation to tokens |
| `resolve_peptide_notation` | evidence ladder + mass arbitration |
| `peptide_fragment_forms` | backbone / cap forms |
| `mass_arbitration` | dual-convention mass check |
| `render_pages` / `render_page` | contact sheets / single pages |
| `record_structure_detection` | validated page decisions |
| `record_measurement_discovery` | assay pages and names |
| `record_assay_reconciliation` | assay-name merge/drop/rename |
| `ocr_pages` | paddle VL-1.6 markdown |
| `upload_pdf` / `start_full_pipeline` / `task_status` / `download_task_result` | server pipeline |
| `build_extraction_report` | markdown report |
| `batch_partition` / `batch_claim` / `batch_complete` / `batch_merge` | parallel coordination |
| `sar_build` / `sar_analysis` | SAR table and potency ranking |
| `open_review_workspace` | frontend review URL |

## Configuration

| variable | default | purpose |
|---|---|---|
| `BIOCHEMINSIGHT_URL` | `http://127.0.0.1:8000` | pipeline API |
| `BIOCHEMINSIGHT_HARNESS_URL` | `http://127.0.0.1:8011` | chemistry endpoints |
| `PADDLEOCR_URL` | `http://127.0.0.1:8010` | paddle VL-1.6 |

The deployment can be on another server; the harness is a pure client.

## Design

- Perception is the agent's job, validated by pydantic contracts.
- Deterministic chemistry reports named gaps, never guesses.
- The paddle client chunks submissions to fit client timeouts and cancels
  abandoned server jobs.
- Structure pages are excluded from assay discovery; the stages share
  findings through `exclude_pages`.
- Detection results are cached per document.
