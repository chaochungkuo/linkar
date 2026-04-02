# linkar

`linkar` is a lightweight runtime for reusable computational templates, with a human-friendly CLI and a machine-readable execution model designed for reliable AI-agent use. The current implementation provides:

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
pipx install git+https://github.com/jovesus/linkar.git
```

Alternative for `uv` users:

```bash
uv tool install git+https://github.com/jovesus/linkar.git
```

Then start with the shortest useful flow:

```bash
linkar project init --name demo
cd demo
linkar pack add ./examples/packs/basic --id basic
linkar run simple_echo --name Linkar
linkar inspect run simple_echo_001
```

In project mode, Linkar exposes a stable directory such as `./simple_echo`, writes results under `results/`, and keeps immutable run history plus metadata under `.linkar/runs/<instance_id>/`.

For ad hoc runs without a project:

```bash
linkar run simple_echo \
  --pack ./examples/packs/basic \
  --param name=Linkar
```

Pack scope is intentionally project-first:

- `linkar run TEMPLATE --pack ...` is ad hoc and does not require a project
- `linkar pack ...` manages packs saved in the current project's `project.yaml`
- `linkar config pack ...` manages global packs saved in user config

Pack lookup precedence is:

1. explicit `--pack`
2. project-configured packs
3. global/user-configured packs

Example global setup:

```bash
linkar config pack add ~/github/izkf_genomics_pack --id izkf_genomics_pack
linkar config pack list
linkar run fastqc --input sample.fastq.gz
```

Use `linkar run TEMPLATE ...` when you want the generic path-or-pack execution interface.

## Local API

Linkar also exposes a small local JSON API over the same core semantics:

```bash
linkar serve --port 8000
```

Current agent-oriented endpoints:

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

Success responses use:

```json
{"ok": true, "data": {...}}
```

Error responses use:

```json
{"ok": false, "error": {"code": "param_resolution_error", "message": "..."}}
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
  - includes `simple_echo`, `simple_file_input`, `simple_boolean_flag`, `download_test_data`, `fastq_stats`, `pixi_echo`, and `pixi_pytest`
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
