---
title: CLI, API, and MCP interfaces
description: The same runtime semantics are exposed to humans, local API clients, and agent tooling.
order: 6
---

Linkar has three interface layers:

- CLI
- local HTTP API
- stdio MCP server

They are meant to expose the same runtime model, not three different products.

## CLI semantics

The CLI is intentionally thin.

Important commands:

- `linkar run ...`
- `linkar render ...`
- `linkar collect ...`
- `linkar test ...`
- `linkar inspect run ...`
- `linkar project ...`
- `linkar pack ...`
- `linkar config pack ...`
- `linkar config author ...`
- `linkar completion ...`

Key behavior:

- `run` always executes
- `render` always stages only
- render-mode templates reuse the visible project bundle on `run`; pass `--refresh` to rerender first
- `collect` records outputs after manual execution
- `project remove-run` can detach or delete recorded runs
- `project prune` can collapse older duplicate-path history while keeping the newest visible run
- `config author` stores reusable author defaults for new projects

If you want the end-to-end mental model first, read `Project lifecycle` before the more detailed
runtime pages.

Run references accepted across `collect`, `inspect run`, `project view`, and `project remove-run` are:

- instance ids such as `fastqc_001`
- unique template ids within a project such as `fastqc`
- run directory paths
- `.linkar/meta.json` paths

## Help and shell completion

The main CLI and dynamic template subcommands use the same Rich help style.

Shell completion supports:

```bash
linkar completion bash
linkar completion zsh
linkar completion fish
linkar completion install bash
linkar completion install zsh
linkar completion install fish
```

`completion install` is the side-effecting path. The plain shell commands only print completion
code.

Existing projects can also manage their own stored author metadata without reinitializing:

```bash
linkar project author show
linkar project author set --name "Project Owner" --email "owner@example.org"
linkar project author clear
```

## Local API

The local HTTP server is not a separate orchestration layer. It is a thin JSON wrapper around the
same core semantics:

```bash
linkar serve --port 8000 --api-token local-dev:read,resolve,execute
```

Start discovery with:

```bash
curl -H 'Authorization: Bearer local-dev' http://127.0.0.1:8000/v1
curl -H 'Authorization: Bearer local-dev' http://127.0.0.1:8000/v1/schema
```

Recommended v1 routes:

- `GET /v1`
- `GET /v1/schema`
- `GET /v1/projects/current`
- `GET /v1/projects/current/runs`
- `GET /v1/projects/current/assets`
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

Important conventions:

- collection responses expose `items` and `count`
- detail responses expose a `kind` field
- `:resolve` returns provenance, warnings, confirmation metadata, and a short-lived `resolve_token` when the plan is ready
- `:run` can still accept direct params, but the preferred v1 pattern is `resolve -> confirm -> run`

Legacy unversioned routes still exist for backward compatibility, but new clients should prefer `/v1/...`.

## MCP

The MCP server exposes the same runtime to agent clients:

```bash
linkar mcp serve
```

Representative MCP tools:

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

For Codex-style clients, the main advantage of MCP is that it exposes small explicit tools instead
of forcing the client to wrap shell commands or raw HTTP itself.

If `linkar` is already installed, a typical Codex setup looks like:

```bash
codex mcp add linkar -- linkar mcp serve
```

If you are working from a repo checkout instead:

```bash
codex mcp add linkar \
  --env PYTHONPATH=/path/to/linkar/src \
  -- python3 -m linkar.mcp_server
```

Then verify it with:

```bash
codex mcp list
codex mcp get linkar
```

The product value here is consistency: humans and agents are using the same underlying contract.
