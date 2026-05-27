---
title: CLI reference
description: Commands, subcommands, common examples, and structured output support for the Linkar CLI.
order: 11
---

This page is the command lookup table. Use the task-oriented guides when you want a worked path;
use this reference when you know the command family you need.

Most commands accept `-h` or `--help`. Commands that produce runtime or project data generally also
support `--format json` and `--format yaml` for automation.

## Execution commands

| Command | Purpose | Common examples |
| --- | --- | --- |
| `linkar run TEMPLATE` | Execute a template. Render-mode templates reuse the visible project bundle unless `--refresh` is passed. | `linkar run demultiplex --param run_name=HLMCNDRX7`<br />`linkar run methods --refresh` |
| `linkar render TEMPLATE` | Stage a standalone editable bundle without executing it. | `linkar render demultiplex --outdir ./demultiplex` |
| `linkar collect RUN_REF` | Refresh declared outputs after manual execution. | `linkar collect ./demultiplex`<br />`linkar collect fastqc_001 --format yaml` |
| `linkar clean TARGET` | Remove template-declared disposable runtime artifacts. | `linkar clean . --dry-run`<br />`linkar clean .`<br />`linkar clean ./demultiplex --yes` |
| `linkar inspect run RUN_REF` | Inspect recorded metadata, params, outputs, warnings, and provenance. | `linkar inspect run fastqc_001`<br />`linkar inspect run ./fastqc --format yaml` |
| `linkar test TEMPLATE` | Run a template-local `test.sh` or `test.py` through Linkar. | `linkar test fastqc --pack ./examples/packs/basic` |

Run and render share the common options `--pack`, `--binding`, `--project`, `--outdir`,
`--param KEY=VALUE`, `--prompt/--no-prompt`, and `--format`. `run` also supports `--verbose` and
`--refresh`.

## Project commands

| Command | Purpose | Common examples |
| --- | --- | --- |
| `linkar project init` | Create `project.yaml` in the target directory. | `linkar project init --name study`<br />`linkar project init --name study --adopt /path/to/run` |
| `linkar project runs` | List runs recorded in `project.yaml`. | `linkar project runs`<br />`linkar project runs --format yaml` |
| `linkar project view` | Show project metadata and recorded runs. | `linkar project view`<br />`linkar project view fastqc_001 --format yaml` |
| `linkar project latest RUN_REF` | Return the newest matching recorded run. | `linkar project latest fastqc`<br />`linkar project latest ./methods` |
| `linkar project adopt-run RUN_REF` | Import existing Linkar run directories into the active project. | `linkar project adopt-run /path/to/run` |
| `linkar project remove-run RUN_REF` | Remove a run record, optionally deleting files. | `linkar project remove-run fastqc_001`<br />`linkar project remove-run fastqc --delete-files` |
| `linkar project prune` | Remove stale duplicate-path history. | `linkar project prune --dry-run`<br />`linkar project prune --keep 2` |
| `linkar project author ...` | Manage author metadata stored in `project.yaml`. | `linkar project author show`<br />`linkar project author set --name "Project Owner"` |

Accepted run references across `collect`, `inspect run`, `project view`, `project latest`, and
`project remove-run` include instance ids, unique template ids, visible project paths, run directory
paths, and `.linkar/meta.json` paths when unambiguous.

## Pack commands

Project packs are saved in `project.yaml`. Global packs are saved in the user-level Linkar config.
Use project packs when a project should carry its pack setup with it. Use global packs for personal
defaults.

| Scope | Command | Purpose |
| --- | --- | --- |
| Project | `linkar pack add REF --id ID` | Add a pack to the active project. |
| Project | `linkar pack list` | List packs saved in the project. |
| Project | `linkar pack use ID` | Select the active/default pack for the project. |
| Project | `linkar pack show` | Show the active/default project pack. |
| Project | `linkar pack status` | Show pack locks and locally known update status. |
| Project | `linkar pack update` | Fetch and fast-forward cached remote project packs. |
| Project | `linkar pack remove ID` | Remove a configured project pack. |
| Global | `linkar config pack add REF --id ID` | Add a pack to user-level config. |
| Global | `linkar config pack list` | List global packs. |
| Global | `linkar config pack use ID` | Select the active global pack. |
| Global | `linkar config pack show` | Show the active global pack. |
| Global | `linkar config pack update` | Fetch and fast-forward cached remote global packs. |
| Global | `linkar config pack remove ID` | Remove a configured global pack. |

Common examples:

```bash
linkar config pack add github:IZKF-Genomics/izkf_pack --id izkf_pack
linkar config pack use izkf_pack
linkar pack add github:IZKF-Genomics/izkf_pack --id izkf_pack --binding default
linkar pack status
linkar pack update izkf_pack
```

## Discovery and automation commands

| Command | Purpose | Common examples |
| --- | --- | --- |
| `linkar templates` | List templates visible from explicit packs and the active project configuration. | `linkar templates`<br />`linkar templates --pack ./examples/packs/basic --format yaml` |
| `linkar serve` | Expose the local project/runtime API over HTTP. | `linkar serve --port 8000 --api-token local-dev:read,resolve,execute` |
| `linkar mcp serve` | Start the stdio MCP server for agent clients. | `linkar mcp serve` |
| `linkar completion bash/zsh/fish` | Print shell completion scripts. | `linkar completion zsh` |
| `linkar completion install bash/zsh/fish` | Install completion in a user-level shell location. | `linkar completion install zsh` |
| `linkar config author ...` | Manage default author metadata for new projects. | `linkar config author set --name "Your Name" --email "you@example.org"` |

Use `linkar templates` before `run` or `render` when you want to verify which pack and template id
will be visible from the current project context.
