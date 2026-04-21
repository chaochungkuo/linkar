---
title: Project lifecycle
description: A practical end-to-end view of how projects move from initialization to cleanup.
order: 4
---

This page is the shortest way to understand how a typical Linkar project evolves over time.

## The common flow

For most project work, the lifecycle is:

1. `project init`
2. attach or select packs
3. `render` when you want an editable bundle
4. `run` when you want Linkar to execute the template
5. `collect` after manual execution of a rendered bundle
6. `inspect run` to review metadata and provenance
7. `project latest` when you want the newest active recorded run
8. `project prune` when stale duplicate-path history accumulates

## Step 1: initialize a project

Create a new project directory with `project.yaml`:

```bash
linkar project init --name study
cd study
```

At this point the project ledger exists, but it contains no recorded runs yet.

## Step 2: attach packs

Projects can use:

- explicit `--pack` references on a single command
- project-local packs stored in `project.yaml`
- global packs from user config

Typical project-local setup:

```bash
linkar pack add /path/to/pack --id my_pack
linkar pack list
```

## Step 3: render an editable bundle

Use `render` when you want to stage files without executing them:

```bash
linkar render demultiplex --outdir ./demultiplex
```

This is especially useful when:

- the generated `run.sh` should be reviewed or edited
- downstream execution happens on another machine
- a user wants to inspect the exact command before running it

Rendered bundles are recorded in `project.yaml` with `state: rendered`.

## Step 4: run a template

Use `run` when Linkar should execute the template:

```bash
linkar run demultiplex
```

For ordinary run-mode templates, Linkar typically keeps:

- a visible project-facing path such as `./demultiplex`
- immutable run history under `.linkar/runs/<instance_id>`

For templates declared with `run.mode: render`, the behavior is different:

- `run` executes directly in the visible project path
- the visible bundle is reused by default
- `--refresh` rerenders the bundle before execution

Example:

```bash
linkar run methods --outdir ./methods --refresh
```

## Step 5: collect outputs after manual execution

If a user runs a rendered `run.sh` manually, Linkar can still refresh outputs and metadata:

```bash
linkar collect ./demultiplex
```

`collect` updates declared outputs in:

- `.linkar/meta.json`
- `project.yaml` when the run belongs to the active project

The CLI now tells you whether the active project ledger was updated or left unchanged, so it is
easier to distinguish:

- collected outputs for a project-registered run
- collected outputs for an ad hoc run outside any active project

Accepted run references include:

- instance ids such as `fastqc_001`
- unique template ids when unambiguous in the project
- run directory paths
- `.linkar/meta.json` paths

## Step 6: inspect provenance

Use `inspect run` to read recorded metadata:

```bash
linkar inspect run fastqc_001
linkar inspect run fastqc
linkar inspect run ./fastqc
```

This is the primary way to answer:

- what params were resolved
- what command was executed
- what outputs were collected
- what warnings were recorded

## Step 7: ask for the newest active recorded run

Sometimes you do not want the whole history. You only want the newest recorded run for a template
or visible path.

Use:

```bash
linkar project latest methods
linkar project latest ./methods
```

This is useful when:

- a template has been rerun several times
- you want the current visible run quickly
- you want a stable precursor before `inspect run` or export logic

## Step 8: prune stale history

Over time, rerendering or replacing visible bundles can leave older duplicate-path entries in
`project.yaml`.

Use:

```bash
linkar project prune --dry-run
linkar project prune
```

By default, `project prune`:

- keeps the newest run for each visible project path
- removes stale duplicate-path entries from `project.yaml`
- deletes orphaned historical run directories for the pruned entries

Use `--keep-files` if you only want to clean metadata and keep directories on disk.

## Practical rule of thumb

Use:

- `render` when you want an editable workspace
- `run` when Linkar should execute now
- `collect` when execution happened outside Linkar
- `inspect run` when you need provenance
- `project prune` when history has become cluttered

## Related pages

- `Project runs and metadata` explains what is recorded in `project.yaml` and `.linkar/`
- `Template runtime contract` explains how templates declare run behavior
- `Interfaces and automation` explains how the CLI, API, and MCP share the same semantics
