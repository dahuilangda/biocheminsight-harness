# biocheminsight-harness

Parse patent and literature compound data — structures, peptide sequences,
structure-activity tables — from inside coding agents via natural language.

No API keys. No model configuration. The coding plan's tokens are the model.

## Quick start

Paste the repo URL into your coding agent's input box:

```
https://github.com/dahuilangda/biocheminsight-harness
```

The agent clones, installs, and registers the MCP server. Then tell it
where your BioChemInsight deployment is:

```
连接到 https://your-host:6066，用户 biochem，密码 <部署时设置的密码>
```

Credentials are saved to `~/.biocheminsight/config.json` and used for
every call (or set `BIOCHEMINSIGHT_USER` / `BIOCHEMINSIGHT_PASS`).
Keep polling while requests are pending: a perception call waits as long
as `task_status` keeps asking about the task and continues in place the
moment its answer lands. A request without `sheet_url` is a text question
whose `prompt` is the whole request; nothing on the server needs a model
endpoint for a run driven this way. After `PERCEPTION_WAIT_SECONDS` (default 60)
without a poll the task moves to `awaiting_perception`, and the run
starts again from the top once you answer, replaying every answered
request from the cache.

Then ask:

```
帮我解析 your-patent.pdf 这篇专利，输出结构、序列和活性数据，给一份报告
```

That's it. No manual pip install, no MCP config file, no environment
variables — the agent handles all of it.

### Manual install (optional)

```bash
git clone https://github.com/dahuilangda/biocheminsight-harness.git
cd biocheminsight-harness
pip install -e ".[dev]"
export BIOCHEMINSIGHT_URL=http://your-server:8000
```

MCP config (if your agent requires explicit registration):

```json
{ "mcpServers": { "biocheminsight-harness": { "command": "biocheminsight-harness" } } }
```

## How it works

```
you ──natural language──▶ coding agent
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
  answer perception     evidence ladder      mass arbitration
  requests (sheets      (RDKit)              (dual convention)
  rendered server-side)
        │                    │                    │
        ▼                    ▼                    ▼
   agent vision          named gaps           verified rows
```

The deployment renders pages and crops, ships every sheet with its
question, and the agent answers from what is visibly printed. Without a
deployment, the harness renders pages itself (`pdftoppm`/`pdfimages`) and
the agent reads them directly. Deterministic chemistry validates every
answer: mass arbitration rejects wrong readings, named gaps surface
unknown tokens, chart data is transcribed from printed values only. No
API keys, no model configuration — the coding plan's tokens are the model.

See [WORKFLOW.md](WORKFLOW.md) for the full procedure.

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
| `configure_deployment` | connect to a BioChemInsight server |
| `deployment_status` | check connectivity |
| `parse_peptide_notation` | notation to tokens |
| `resolve_peptide_notation` | evidence ladder + mass arbitration |
| `peptide_fragment_forms` | backbone / cap forms |
| `mass_arbitration` | dual-convention mass check |
| `render_pages` / `render_page` | contact sheets / single pages (local mode; the deployment renders otherwise) |
| `extract_page_images` | native chart crops for vision reading |
| `route_pages` | paddle/vision dispatch with quality escalation |
| `record_structure_detection` | validated page decisions |
| `record_measurement_discovery` | assay pages and names |
| `record_assay_reconciliation` | assay-name merge/drop/rename |
| `verify_extraction` | cross-check independent readings |
| `record_monomer_dictionary` | document-scoped residue codebook (your vision OCSR) |
| `verify_dual_source` | InChIKey agreement for structure second-source |
| `fetch_perception_sheet` | download a perception sheet image |
| `task_tables` | read structures/assays/merged/sar inline |
| `cancel_task` | cancel a running pipeline |
| `parse_sequence` / `smiles_to_sequence` | sequence chemistry via deployment |
| `verify_structure` | visual verification of a decode vs its crop |
| `detect_structures_on_page` | MolDetv2 bounding boxes on a rendered page |
| `recognize_region` | MolSight recognition of a boxed region |
| `measurement_review_start` / `measurement_review_submit` | measurement review session |
| `task_artifact_urls` | browser URLs for finished tables |
| `batch_fail` | release a failed batch for another worker |
| `ocr_pages` | paddle VL-1.6 markdown |
| `upload_pdf` / `start_full_pipeline` / `task_status` / `download_task_result` | server pipeline |
| `build_extraction_report` | markdown report |
| `batch_partition` / `batch_claim` / `batch_complete` / `batch_merge` | parallel coordination |
| `sar_build` / `sar_analysis` | SAR table and potency ranking |
| `open_review_workspace` | frontend review URL |

## Perception routing

Mode is declared by the caller, not sniffed: `start_full_pipeline`
always declares agent perception — every model call of the run, with an
image or text only, becomes a request; the pipeline waits at
`awaiting_perception` for its answer, the pending requests ride in
`task_status` as bounded batches (`BIOCHEMINSIGHT_PERCEPTION_BATCH`,
default 8), and the task resumes on its own after the last answer.
Standalone API callers get the configured models by default and never
see the protocol. The
`pipeline_perception_requests` / `pipeline_perception_answer` tools
remain for agents that prefer explicit polling.

## Configuration

| variable | default | purpose |
|---|---|---|
| `BIOCHEMINSIGHT_URL` | `http://127.0.0.1:8000` | pipeline API |
| `BIOCHEMINSIGHT_HARNESS_URL` | `http://127.0.0.1:8011` | chemistry endpoints |
| `PADDLEOCR_URL` | `http://127.0.0.1:8010` | paddle VL-1.6 |
| `BIOCHEMINSIGHT_PERCEPTION_BATCH` | `8` | pending perception requests surfaced per poll |

Persisted in `~/.biocheminsight/config.json` via `configure_deployment`;
environment variables override.

When the harness runs on the deployment's own host, point the two URLs at
a local address. A public name that resolves to a relay costs 1-5 s per call
and turns a 2 MB upload into many seconds; `deployment_status` reports the
round-trip time of each endpoint and says so.
