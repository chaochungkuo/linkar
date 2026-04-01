---
title: Using Linkar from agents and automation
description: Prefer the core helpers or the local API when an agent needs to inspect templates, run work, and read structured results.
order: 3
status: ready
---

Linkar is designed for two interfaces:

- a short CLI for humans
- a structured core and local API for machines and AI agents

If you are building an agent or automation layer, prefer the machine-facing interfaces over shell
scraping.

## Best order of operations

1. Inspect available templates
2. Inspect project runs and outputs
3. Choose or resolve params explicitly
4. Trigger execution
5. Read back metadata and outputs from the structured result

## Core helper path

For Python-based agents, use the core helpers directly:

```python
from linkar.core import inspect_run, list_templates, run_template

templates = list_templates(pack_refs=["./examples/packs/basic"])
result = run_template(
    "simple_echo",
    params={"name": "Agent"},
    pack_refs=["./examples/packs/basic"],
)
metadata = inspect_run(result["outdir"])
```

This avoids terminal parsing and keeps the semantics aligned with the CLI.

## Local API path

If the agent is outside Python or needs process isolation, start the local API:

```bash
linkar serve --port 8000
```

Then inspect and run through JSON:

```bash
curl -s "http://127.0.0.1:8000/templates?pack=./examples/packs/basic"
curl -s "http://127.0.0.1:8000/templates/simple_echo?pack=./examples/packs/basic"
curl -s -X POST "http://127.0.0.1:8000/resolve" \
  -H "Content-Type: application/json" \
  -d '{"template":"simple_echo","pack_refs":["./examples/packs/basic"],"params":{"name":"Agent"}}'
curl -s -X POST "http://127.0.0.1:8000/run" \
  -H "Content-Type: application/json" \
  -d '{"template":"simple_echo","pack_refs":["./examples/packs/basic"],"params":{"name":"Agent"}}'
curl -s "http://127.0.0.1:8000/runs/simple_echo_001/outputs?project=./study"
curl -s "http://127.0.0.1:8000/runs/simple_echo_001/runtime?project=./study"
```

Current local API surface:

- `GET /templates`
- `GET /templates/{template_id}`
- `GET /projects/runs`
- `GET /projects/assets`
- `GET /runs/{run_ref}`
- `GET /runs/{run_ref}/outputs`
- `GET /runs/{run_ref}/runtime`
- `GET /methods`
- `POST /resolve`
- `POST /run`
- `POST /test`

Success responses use:

```json
{"ok": true, "data": {...}}
```

Errors use:

```json
{"ok": false, "error": {"code": "param_resolution_error", "message": "..."}}
```

## Why this is better than shell scraping

- parameters are structured
- outputs are structured
- errors are typed JSON or typed Python exceptions
- the same runtime path is used by CLI, core, and API
- the run artifact still lives on disk in a normal directory

## Human fallback

The CLI is still the right interface for quick interactive work:

```bash
linkar run simple_echo --pack ./examples/packs/basic --param name=Human
```

But once an agent needs repeated inspection and execution, the core helpers or the local API are
the cleaner path.
