# linkar

`linkar` stands for `LINKing All Resources`.

It is a lightweight runtime for reusable computational templates, with a human-friendly CLI and a machine-readable execution model designed for reliable AI-agent use. The current implementation provides:

- A Python core with pure project and template orchestration logic
- A Click-based CLI with template-aware run commands
- A thin local JSON API over the same core semantics
- A stdio MCP server for tool-oriented agent clients
- YAML-based templates and projects
- Metadata and runtime capture under `.linkar/`

For template authors:

- use `run.command` for thin single-command wrappers
- use `run.sh` only when the template needs real script logic

New template and pack contracts should use:

- `linkar_template.yaml`
- `linkar_pack.yaml`

Linkar still accepts the legacy filenames `template.yaml` and `binding.yaml` for backward compatibility.

## Quickstart

Install Linkar as a CLI tool first.

Recommended:

```bash
pipx install git+https://github.com/chaochungkuo/linkar.git
```

Alternative for `uv` users:

```bash
uv tool install git+https://github.com/chaochungkuo/linkar.git
```

Then start with the shortest useful flow:

```bash
linkar config author set --name "Your Name" --email "you@example.org" --organization "IZKF"
linkar project init --name demo
cd demo
linkar pack add ./examples/packs/basic --id basic
linkar run simple_echo --name Linkar
linkar inspect run simple_echo_001
```

If you already have an ad hoc Linkar run and want to start a project around it:

```bash
linkar project init --name study --adopt /path/to/existing_run
```

In project mode, Linkar exposes a stable directory such as `./simple_echo`, writes results under `results/`, and keeps immutable run history plus metadata under `.linkar/runs/<instance_id>/`. Rendered bundles created inside a project are also recorded in `project.yaml` with `state: rendered`, while executed runs are recorded with execution state such as `completed` or `failed`. For templates whose declared `run.mode` is `render`, `linkar run` inside a project executes directly in the visible project directory instead of creating a `.linkar/runs/...` history path. By default it runs the current rendered bundle if one already exists; use `linkar run TEMPLATE --refresh` to rerender first.

For ad hoc runs without a project:

```bash
linkar run simple_echo \
  --pack ./examples/packs/basic \
  --param name=Linkar
```

Pack scope is intentionally layered:

- `linkar run TEMPLATE --pack ...` is ad hoc and does not require a project
- `linkar pack ...` manages packs saved in the current project's `project.yaml`
- `linkar config pack ...` manages global packs saved in user config

Pack lookup precedence is:

1. explicit `--pack`
2. project-configured packs
3. global/user-configured packs

That means a new project without its own `packs:` entries can still use your global configured
packs. You only need `linkar pack add ...` when this project should use a different pack set, save a
project-specific binding, or carry its pack configuration with the project itself.

Example global setup:

```bash
linkar config pack add ~/github/izkf_genomics_pack --id izkf_genomics_pack
linkar config author set --name "Your Name" --email "you@example.org"
linkar config pack list
linkar run fastqc --input sample.fastq.gz
```

Use `linkar run TEMPLATE ...` when you want the generic path-or-pack execution interface.

## Local API

Linkar also exposes a local JSON API over the same core semantics as the CLI.

Start it without auth for trusted local use:

```bash
linkar serve --port 8000
```

Or start it with bearer-token auth:

```bash
linkar serve --port 8000 --api-token local-dev:read,resolve,execute
```

The first call an agent or script should usually make is:

```bash
curl http://127.0.0.1:8000/v1
curl http://127.0.0.1:8000/v1/schema
```

With auth enabled:

```bash
curl -H 'Authorization: Bearer local-dev' http://127.0.0.1:8000/v1
```

Recommended v1 routes:

- `GET /v1`
- `GET /v1/schema`
- `GET /v1/health`
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

Legacy unversioned routes still exist for backward compatibility, but new clients should prefer `/v1/...`.

Success responses use:

```json
{"ok": true, "data": {...}}
```

Error responses use:

```json
{"ok": false, "error": {"code": "param_resolution_error", "message": "..."}}
```

V1 conventions:

- collection responses expose `items` and `count`, while keeping compatibility keys like `templates`, `runs`, or `assets`
- major detail responses expose a `kind` field such as `service`, `project`, `template`, `run`, `run_outputs`, or `run_status`
- `POST /v1/templates/{template_id}:resolve` returns `param_provenance`, `warnings`, `confirmation`, and a short-lived `resolve_token` when the plan is ready
- `POST /v1/templates/{template_id}:run` accepts either direct params or a `resolve_token`; when using a `resolve_token`, pass `{"confirm": true}`

Typical agent-friendly flow:

```bash
curl -H 'Authorization: Bearer local-dev' \
  'http://127.0.0.1:8000/v1/projects/current?project=/data/projects/my_project'

curl -H 'Authorization: Bearer local-dev' \
  -H 'Content-Type: application/json' \
  -d '{"project":"/data/projects/my_project","params":{"name":"Linkar"}}' \
  http://127.0.0.1:8000/v1/templates/simple_echo:resolve
```

Then use the returned `resolve_token`:

```bash
curl -H 'Authorization: Bearer local-dev' \
  -H 'Content-Type: application/json' \
  -d '{"resolve_token":"TOKEN_FROM_RESOLVE","confirm":true}' \
  http://127.0.0.1:8000/v1/templates/simple_echo:run
```

## MCP for agent clients

Linkar also exposes a local stdio MCP server over the same core semantics.

Install the optional dependency if you want the MCP bridge:

```bash
pip install 'linkar[mcp]'
```

Then start it with either entrypoint:

```bash
linkar mcp serve
```

or:

```bash
linkar-mcp
```

High-value MCP tools include:

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

## Linkar Repo Development

These commands are for working on the `linkar` engine repo itself, not for normal Linkar usage.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest
```

Or with `pixi`:

```bash
pixi run test
pixi run cli-help
pixi run serve
```

## Example Packs

Bundled examples are organized by teaching purpose:

- `examples/packs/basic`
  - minimal templates and local authoring patterns
  - includes `simple_echo`, `simple_file_input`, `simple_boolean_flag`, `download_test_data`, `fastq_stats`, `glob_reports`, `portable_python`, `pixi_echo`, and `pixi_pytest`
  - `simple_echo` demonstrates `run.command`; the others show script-based templates
- `examples/packs/chaining`
  - a small project-mode pack showing output reuse through a default binding
- `examples/packs/pack_management`
  - two tiny packs with the same template id to demonstrate active-pack selection
- `examples/packs/binding_overrides`
  - a small pack showing the difference between a default binding and an explicit override binding
- `examples/packs/remote`
  - a tiny pack intended for Git-backed remote asset demonstrations

Typical progression:

```bash
linkar test simple_echo --pack ./examples/packs/basic
linkar test simple_file_input --pack ./examples/packs/basic
linkar test simple_boolean_flag --pack ./examples/packs/basic
linkar test download_test_data --pack ./examples/packs/basic
linkar test fastq_stats --pack ./examples/packs/basic
linkar test glob_reports --pack ./examples/packs/basic
linkar test portable_python --pack ./examples/packs/basic
```

The basic pack is for didactic templates. Real domain templates should live in a dedicated external pack such as `izkf_genomics_pack`.

## Website

The demo/docs site now lives in `website/` and is built with Astro for GitHub Pages.

Use Node 22 there:

```bash
cd website
npm install
npm run dev
```

The GitHub Pages workflow is in `.github/workflows/deploy-pages.yml`.
