---
title: Local API reference
description: A practical reference for Linkar's local HTTP API, including auth, discovery, route conventions, and the resolve-confirm-run flow.
order: 7
---

Linkar's local HTTP API exposes the same runtime semantics as the CLI.

Use it when:

- an agent needs structured inspection instead of shell parsing
- a service wants to trigger templates remotely on the same server
- you want a stable machine-facing contract around projects, templates, and runs

## Start the server

For trusted local use:

```bash
linkar serve --port 8000
```

With bearer-token auth:

```bash
linkar serve --port 8000 --api-token local-dev:read,resolve,execute
```

The `--api-token` option accepts `TOKEN[:ROLES]` and can be repeated.

Available roles:

- `read`
- `resolve`
- `execute`

## First calls to make

Start with discovery:

```bash
curl http://127.0.0.1:8000/v1
curl http://127.0.0.1:8000/v1/schema
```

With auth enabled:

```bash
curl -H 'Authorization: Bearer local-dev' http://127.0.0.1:8000/v1
curl -H 'Authorization: Bearer local-dev' http://127.0.0.1:8000/v1/schema
```

The running server also exposes a live HTML reference page at:

```text
/v1/docs
```

## Response conventions

Success envelope:

```json
{"ok": true, "data": {...}}
```

Error envelope:

```json
{"ok": false, "error": {"code": "param_resolution_error", "message": "..."}}
```

Collection conventions:

- `items` contains the canonical collection entries
- `count` gives the item count
- compatibility keys such as `templates`, `runs`, and `assets` still exist

Detail conventions:

- major detail responses expose a `kind` field
- examples include `service`, `project`, `template`, `run`, `run_outputs`, and `run_status`

## Recommended v1 routes

Discovery:

- `GET /v1`
- `GET /v1/schema`
- `GET /v1/docs`
- `GET /v1/health`

Project scope:

- `GET /v1/projects/current`
- `GET /v1/projects/current/runs`
- `GET /v1/projects/current/assets`

Template scope:

- `GET /v1/templates`
- `GET /v1/templates/{template_id}`
- `POST /v1/templates/{template_id}:resolve`
- `POST /v1/templates/{template_id}:run`
- `POST /v1/templates/{template_id}:render`
- `POST /v1/templates/{template_id}:test`

Run scope:

- `GET /v1/runs/{run_ref}`
- `GET /v1/runs/{run_ref}/outputs`
- `GET /v1/runs/{run_ref}/status`
- `GET /v1/runs/{run_ref}/runtime`

Legacy unversioned routes still exist for backward compatibility, but new clients should prefer `/v1/...`.

## Resolve, then run

The preferred v1 execution path is:

1. inspect the project and template
2. call `:resolve`
3. review `resolved_params`, `param_provenance`, `warnings`, and `confirmation`
4. if `ready: true`, use the returned `resolve_token`
5. call `:run` with `confirm: true`

Resolve example:

```bash
curl -X POST http://127.0.0.1:8000/v1/templates/simple_echo:resolve \
  -H 'Authorization: Bearer local-dev' \
  -H 'Content-Type: application/json' \
  -d '{"pack_refs":["./examples/packs/basic"],"params":{"name":"Agent"}}'
```

The response includes:

- `resolved_params`
- `param_provenance`
- `unresolved_params`
- `warnings`
- `confirmation`
- `resolve_token` when the plan is ready

Then confirm and run:

```bash
curl -X POST http://127.0.0.1:8000/v1/templates/simple_echo:run \
  -H 'Authorization: Bearer local-dev' \
  -H 'Content-Type: application/json' \
  -d '{"resolve_token":"TOKEN_FROM_RESOLVE","confirm":true}'
```

## Example project flow

Inspect the current project:

```bash
curl -H 'Authorization: Bearer local-dev' \
  'http://127.0.0.1:8000/v1/projects/current?project=/data/projects/my_project'
```

List recorded runs:

```bash
curl -H 'Authorization: Bearer local-dev' \
  'http://127.0.0.1:8000/v1/projects/current/runs?project=/data/projects/my_project'
```

Inspect a run:

```bash
curl -H 'Authorization: Bearer local-dev' \
  'http://127.0.0.1:8000/v1/runs/my_run_001?project=/data/projects/my_project'
```

Read run outputs:

```bash
curl -H 'Authorization: Bearer local-dev' \
  'http://127.0.0.1:8000/v1/runs/my_run_001/outputs?project=/data/projects/my_project'
```

## Why this matters for agents

The API is structured so an agent can:

- discover what Linkar can do
- inspect template contracts
- understand project context
- resolve params with provenance
- ask for confirmation before execution
- inspect outputs and status without shell parsing

That is the main value of the local API: it makes Linkar legible to both humans and machines.
