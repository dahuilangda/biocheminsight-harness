# biocheminsight-harness

Agent toolkit for BioChemInsight: patent and literature parsing driven from
coding agents (Claude Code, Codex, ZCode and anything speaking MCP).

## Layout

```
src/biocheminsight_harness/
  chemistry.py     harness client: notation parsing, evidence ladder, fragment contracts, mass arbitration
  client.py        REST client for a running BioChemInsight deployment
  ocr.py           paddle VL-1.6 service client (chunked, cancel-aware)
  pages.py         page and contact-sheet rendering
  decisions.py     pydantic contracts for perception answers
  report.py        markdown report from a finished run
  mcp_server.py    MCP server exposing the tools
skills/            agent skill documents
tests/
```

## Conventions

- Python 3.11+, stdlib style, type hints on public functions.
- Comments only where the code cannot say it; no narration.
- Tests run offline: `pytest -q`. The chemistry client tests use a mock
  transport; no deployment is needed.
- Perception is supplied by the agent (see `skills/`), never by configured
  model keys.
