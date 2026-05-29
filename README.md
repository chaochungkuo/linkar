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

## Documentation

The documentation site is published at <https://chaochungkuo.github.io/linkar/>.

Use it as the primary technical reference when you want the newest guides and command examples:

- [Getting started](https://chaochungkuo.github.io/linkar/tutorials/getting-started/)
- [Project lifecycle](https://chaochungkuo.github.io/linkar/explanations/project-lifecycle/)
- [Template runtime contract](https://chaochungkuo.github.io/linkar/explanations/template-runtime-contract/)
- [CLI reference](https://chaochungkuo.github.io/linkar/explanations/cli-reference/)
- [Local API reference](https://chaochungkuo.github.io/linkar/explanations/local-api-reference/)

The site is organized as a documentation-first interface rather than a marketing page. Its sidebar
groups pages by task area: Start, Projects, Templates, Automation, and Reference. It also includes a
client-side search box backed by a static `search.json` index, so it works on GitHub Pages without a
server.

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

If you need to override or inspect author metadata on an existing project after initialization:

```bash
linkar project author show
linkar project author set --name "Project Owner" --email "owner@example.org"
linkar project author clear
```

If you already have an ad hoc Linkar run and want to start a project around it:

```bash
linkar project init --name study --adopt /path/to/existing_run
```

In project mode, Linkar exposes a stable directory such as `./simple_echo`, writes results under `results/`, and keeps immutable run history plus metadata under `.linkar/runs/<instance_id>/`. Rendered bundles created inside a project are also recorded in `project.yaml` with `state: rendered`, while executed runs are recorded with execution state such as `completed` or `failed`. For templates whose declared `run.mode` is `render`, `linkar run` inside a project executes directly in the visible project directory instead of creating a `.linkar/runs/...` history path. By default it runs the current rendered bundle if one already exists; use `linkar run TEMPLATE --refresh` to rerender first.

Command model:

- `linkar run ...` executes a template
- `linkar render ...` stages a bundle without executing it; the target directory must be empty or absent
- `linkar collect RUN_REF` refreshes declared outputs after manual execution
- `linkar clean .` removes template-declared runtime artifacts from a project or rendered template directory
- `linkar inspect run RUN_REF` reads recorded metadata
- `linkar project prune` removes stale duplicate-path history

`RUN_REF` accepts an instance id such as `fastqc_001`, a unique template id within the project such as `fastqc`, a run directory path, or a `.linkar/meta.json` path.

For execution-style commands such as `run`, `render`, `collect`, and `test`:

- the default plain stdout is the primary workspace or run directory path
- use `--format json` or `--format yaml` when you want stable structured output

`clean` is intentionally driven by template metadata, not by Linkar built-ins. A
template can declare disposable artifacts in `linkar_template.yaml`:

```yaml
cleanup:
  - path: .pixi
    type: dir
  - glob: ".nextflow.log*"
    type: file
```

`linkar clean .` works from either a project root or a rendered template
directory. When a current configured pack contains the same template id, Linkar
uses that latest cleanup policy rather than staying pinned to the cleanup rules
recorded when the workspace was rendered. By default it prints the cleanup
candidates and asks for terminal confirmation before deleting anything. Use
`--dry-run` to inspect candidates without deleting them and `--yes` for
non-interactive cleanup.

Typical project lifecycle:

1. `linkar project init --name study`
2. attach project packs with `linkar pack add ...` if needed
3. `linkar render TEMPLATE ...` when you want an editable bundle
4. `linkar run TEMPLATE ...` when you want Linkar to execute it
5. `linkar collect RUN_REF` after manual execution of a rendered bundle
6. `linkar clean . --dry-run` before export or archiving when templates declare disposable runtime artifacts
7. `linkar inspect run RUN_REF` to review provenance
8. `linkar project latest TEMPLATE_ID` when you want the newest active recorded run
9. `linkar project prune` when duplicate-path history accumulates

For a fuller walkthrough, see the website explanation
[Project lifecycle](https://chaochungkuo.github.io/linkar/explanations/project-lifecycle/).

If you accumulate older duplicate run entries for the same visible project path, use:

```bash
linkar project prune --dry-run
linkar project prune
```

By default, `project prune` keeps the newest run per visible path and removes orphaned historical run directories for the pruned entries. Use `--keep-files` if you only want to clean `project.yaml`.
Use `--keep N` when you want to retain the newest `N` runs per visible path instead of only the newest one.

If you only want the newest recorded run for a template or visible path, use:

```bash
linkar project latest fastqc
linkar project latest ./methods
```

From the local API, the project-scoped equivalent is:

```bash
curl -H 'Authorization: Bearer local-dev' \
  'http://127.0.0.1:8000/v1/projects/current/runs/latest?project=/data/projects/my_project&run_ref=methods'
```

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

Git-backed packs are first-class refs. Linkar treats the Git revision as the
pack version source of truth rather than requiring a separate pack-level
semantic version in `linkar_pack.yaml`. Use Git tags when you want a
human-readable release name. The short author-to-user flow looks like this:

```bash
# Template author: develop and test locally.
linkar test scrna_prep --pack ~/github/izkf_pack

# User: install the published pack from GitHub.
linkar config pack add github:IZKF-Genomics/izkf_pack --id izkf_pack
linkar config pack list
linkar templates
linkar run scrna_prep ...

# User: update the cached GitHub checkout when the author publishes changes.
linkar config pack update izkf_pack
```

For the full command guide, see the website tutorial
[Managing Git-backed packs](https://chaochungkuo.github.io/linkar/tutorials/managing-git-backed-packs/).

Use `linkar run TEMPLATE ...` when you want the generic path-or-pack execution interface.

Shell completion can be printed or installed for `bash`, `zsh`, and `fish`:

```bash
linkar completion fish
linkar completion install fish
```

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
- `GET /v1/projects/current/runs/latest`
- `GET /v1/projects/current/assets`
- `GET /v1/templates`
- `GET /v1/templates/{template_id}`
- `POST /v1/templates/{template_id}:resolve`
- `POST /v1/templates/{template_id}:run`
- `POST /v1/templates/{template_id}:render`
- `POST /v1/templates/{template_id}:test`
- `GET /v1/runs/{run_ref}`
- `POST /v1/runs:collect`
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

The documentation site lives in `website/` and is built with Astro for GitHub Pages. It uses a
single docs layout with a left sidebar, an inline SVG logo component, and a static client-side
search index generated at `/search.json`.

Use Node 22 there:

```bash
cd website
npm install
npm run dev
```

Build the production site locally with:

```bash
npm run build
```

The GitHub Pages workflow is in `.github/workflows/deploy-pages.yml`.
