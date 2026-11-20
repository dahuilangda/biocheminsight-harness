# biocheminsight-harness

Agent toolkit for [BioChemInsight](https://github.com/dahuilangda/BioChemInsight):
parse patent and literature compound data — structures, peptide sequences,
structure-activity tables — from inside coding agents (Claude Code, Codex,
ZCode) via natural language.

## Why

A BioChemInsight deployment normally needs its own language-model and
vision-model API keys. Those keys are the expensive part, and a coding agent
already carries both: its subscription tokens *are* the model. This harness
inverts the flow — deterministic chemistry and document IO run in-process,
and the agent supplies the perception and judgment steps out of its own
context. The deployment keys disappear; the agent's tools (image viewing,
report writing, file handling) take over the rest.

## Install

```bash
pip install -e ".[mcp,dev]"
export BIOCHEMINSIGHT_URL=http://your-deployment:8000          # pipeline API
export BIOCHEMINSIGHT_HARNESS_URL=http://your-deployment:8011  # chemistry tools
export PADDLEOCR_URL=http://your-deployment:8010               # paddle VL-1.6
```

BioChemInsight can run on another server; the harness is a pure client and
only needs the three URLs to be reachable.

Register the MCP server with your agent:

```json
{
  "mcpServers": {
    "biocheminsight-harness": {
      "command": "biocheminsight-harness"
    }
  }
}
```

Or drop `skills/biocheminsight-patents` into your agent's skills directory.

## Use

Ask in natural language:

> 帮我解析 WO2025137159 这篇专利，输出结构、序列和活性数据，再给一份报告

The agent follows `skills/biocheminsight-patents/SKILL.md`:

- **server mode** — uploads the PDF, runs the BioChemInsight pipeline,
  downloads the merged bundle, writes a report.
- **agent mode** — renders pages onto contact sheets, reads them itself,
  records per-page decisions, OCRs the selected pages through the paddle
  VL-1.6 service, and resolves peptide rows through the deterministic
  evidence ladder (notation parsing, fragment contracts, mass arbitration).
  No model keys are involved: the agent is the model.

## Tools

| tool | mode | purpose |
|---|---|---|
| `parse_peptide_notation` | chemistry | notation to tokens |
| `resolve_peptide_notation` | chemistry | evidence ladder + mass arbitration |
| `peptide_fragment_forms` | chemistry | backbone / cap contract forms |
| `mass_arbitration` | chemistry | dual-convention mass check |
| `render_pages` / `render_page` | perception | contact sheets and single pages |
| `record_structure_detection` | perception | validated page decisions |
| `record_measurement_discovery` | perception | selected assay pages and names |
| `record_assay_reconciliation` | perception | assay-name merge/drop/rename |
| `ocr_pages` | io | paddle VL-1.6 markdown |
| `upload_pdf` / `start_full_pipeline` / `task_status` / `download_task_result` | server | deployment pipeline |
| `build_extraction_report` | output | markdown report from a run |

## Design notes

- Perception is supplied by the agent, validated by pydantic contracts in
  `decisions.py`; nothing the agent answers is trusted without passing its
  schema.
- Deterministic chemistry fails with named gaps: an unknown residue token or
  a mass mismatch is reported, never guessed.
- The paddle client submits pages in timeout-sized chunks and cancels
  abandoned server jobs, so a slow page cannot clog the serial worker.
