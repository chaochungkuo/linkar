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

Important current commands:

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

Recent behavior worth knowing:

- `run` always executes
- `render` always stages only
- `collect` records outputs after manual execution
- `project remove-run` can detach or delete recorded runs
- `config author` stores reusable author defaults for new projects

## Help and shell completion

The main CLI and dynamic template subcommands now use the same Rich help style.

Shell completion supports:

```bash
linkar completion bash
linkar completion zsh
linkar completion install bash
linkar completion install zsh
```

`completion install` is the side-effecting path. The plain shell commands only print completion
code.

## Local API

The local HTTP server is not a separate orchestration layer. It is a thin JSON wrapper around the
same core semantics:

```bash
linkar serve --port 8000
```

Current high-value endpoints include:

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
- `POST /render`
- `POST /collect`
- `POST /test`

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

The product value here is consistency: humans and agents are using the same underlying contract.
