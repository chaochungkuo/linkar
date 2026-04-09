---
title: Using Linkar from agents and automation
description: Prefer the core helpers or the local API when an agent needs to inspect templates, run work, and read structured results.
order: 7
status: ready
---

Linkar is designed for two interfaces:

- a short CLI for humans
- a structured core, local API, and MCP bridge for machines and AI agents

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
from linkar.core import collect_run_outputs, inspect_run, list_templates, render_template, run_template

templates = list_templates(pack_refs=["./examples/packs/basic"])
result = run_template(
    "simple_echo",
    params={"name": "Agent"},
    pack_refs=["./examples/packs/basic"],
)
metadata = inspect_run(result["outdir"])
bundle = render_template(
    "simple_echo",
    params={"name": "Agent"},
    pack_refs=["./examples/packs/basic"],
    outdir="./simple_echo_bundle",
)
collect_run_outputs("./simple_echo_bundle")
```

This avoids terminal parsing and keeps the semantics aligned with the CLI.

## Local API path

If the agent is outside Python or needs process isolation, start the local API:

```bash
linkar serve --port 8000 --api-token local-dev:read,resolve,execute
```

Start with discovery:

```bash
curl -s -H 'Authorization: Bearer local-dev' \
  "http://127.0.0.1:8000/v1"
curl -s -H 'Authorization: Bearer local-dev' \
  "http://127.0.0.1:8000/v1/schema"
curl -s -H 'Authorization: Bearer local-dev' \
  "http://127.0.0.1:8000/v1/templates?pack=./examples/packs/basic"
curl -s -H 'Authorization: Bearer local-dev' \
  "http://127.0.0.1:8000/v1/templates/simple_echo?pack=./examples/packs/basic"
```

Then resolve before running:

```bash
curl -s -X POST "http://127.0.0.1:8000/v1/templates/simple_echo:resolve" \
  -H 'Authorization: Bearer local-dev' \
  -H "Content-Type: application/json" \
  -d '{"pack_refs":["./examples/packs/basic"],"params":{"name":"Agent"}}'
```

When the response is `ready: true`, take the returned `resolve_token` and confirm the run:

```bash
curl -s -X POST "http://127.0.0.1:8000/v1/templates/simple_echo:run" \
  -H 'Authorization: Bearer local-dev' \
  -H "Content-Type: application/json" \
  -d '{"resolve_token":"TOKEN_FROM_RESOLVE","confirm":true}'
```

If you want a staged bundle without execution:

```bash
curl -s -X POST "http://127.0.0.1:8000/v1/templates/simple_echo:render" \
  -H 'Authorization: Bearer local-dev' \
  -H "Content-Type: application/json" \
  -d '{"pack_refs":["./examples/packs/basic"],"params":{"name":"Agent"},"outdir":"./simple_echo_bundle"}'
```

If you run inside a real project instead of using only `pack_refs`, inspect the project and the recorded run through:

```bash
curl -s -H 'Authorization: Bearer local-dev' \
  "http://127.0.0.1:8000/v1/projects/current?project=./study"
curl -s -H 'Authorization: Bearer local-dev' \
  "http://127.0.0.1:8000/v1/projects/current/runs?project=./study"
curl -s -H 'Authorization: Bearer local-dev' \
  "http://127.0.0.1:8000/v1/runs/simple_echo_001/outputs?project=./study"
curl -s -H 'Authorization: Bearer local-dev' \
  "http://127.0.0.1:8000/v1/runs/simple_echo_001/status?project=./study"
```

Recommended local API surface:

- `GET /v1`
- `GET /v1/schema`
- `GET /v1/projects/current`
- `GET /v1/projects/current/runs`
- `GET /v1/templates`
- `GET /v1/templates/{template_id}`
- `POST /v1/templates/{template_id}:resolve`
- `POST /v1/templates/{template_id}:run`
- `POST /v1/templates/{template_id}:render`
- `POST /v1/templates/{template_id}:test`
- `GET /v1/runs/{run_ref}`
- `GET /v1/runs/{run_ref}/outputs`
- `GET /v1/runs/{run_ref}/status`
- `GET /v1/runs/{run_ref}/runtime`

Success responses use:

```json
{"ok": true, "data": {...}}
```

Errors use:

```json
{"ok": false, "error": {"code": "param_resolution_error", "message": "..."}}
```

The v1 additions that matter most for agents are:

- `kind` on major detail responses
- `items` and `count` on collection responses
- `param_provenance`, `warnings`, and `confirmation` on `:resolve`
- short-lived `resolve_token` support for `:run`

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

## MCP path for tool-oriented clients

If the client already speaks MCP, use Linkar's stdio MCP server instead of wrapping the CLI.

Install the optional dependency:

```bash
pip install 'linkar[mcp]'
```

Then start the server:

```bash
linkar mcp serve
```

or:

```bash
linkar-mcp
```

For Codex, register it once in the shared Codex config:

```bash
codex mcp add linkar -- linkar mcp serve
```

If you are running from a local checkout instead of an installed CLI:

```bash
codex mcp add linkar \
  --env PYTHONPATH=/home/ckuo/github/linkar/src \
  -- python3 -m linkar.mcp_server
```

Then confirm the server is registered:

```bash
codex mcp list
codex mcp get linkar
```

After restarting the Codex session in VS Code, the agent can use the Linkar MCP tools directly.

The MCP tool surface mirrors the same high-value operations:

- `linkar_list_templates`
- `linkar_describe_template`
- `linkar_resolve`
- `linkar_run`
- `linkar_render`
- `linkar_collect`
- `linkar_test`
- `linkar_inspect_run`
- `linkar_get_run_outputs`
- `linkar_get_run_runtime`

This is the cleanest path for Codex-style clients because it exposes small, explicit tools instead
of forcing shell parsing or a second wrapper layer over the HTTP API.

## Pack-side discovery

In some environments the agent also needs help finding likely project paths, FASTQ runs, or local
references before it can call Linkar.

That kind of facility-specific knowledge does not have to go into Linkar core. A site pack can
carry a separate discovery layer instead.

A good split looks like:

- `templates/` for reusable workflows
- `functions/` for binding-time param resolution
- `discovery/` for read-only site-specific inventory helpers

That lets an agent:

1. discover likely project or dataset candidates from the pack
2. choose the right one with the user
3. use Linkar API or MCP tools to resolve and run workflows
