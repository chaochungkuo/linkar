---
title: Project runs and metadata
description: What lives in `project.yaml`, what lives under `.linkar/`, and how run adoption, render, collect, and remove fit together.
order: 5
---

Linkar projects are local working state, not a registry and not a hidden database.

## What a project records

`project.yaml` records:

- project id
- optional author metadata
- attached packs
- active pack
- recorded template runs

A recorded run entry usually contains:

- `id`
- `instance_id`
- `path`
- `history_path`
- `params`
- `outputs`
- `meta`
- `state`
- optional `pack`
- optional `binding`
- optional `adopted`

## Stable path versus immutable history

For `linkar run ...` inside a project, Linkar separates:

- a stable project-facing path such as `./fastqc`
- immutable history under `.linkar/runs/fastqc_001`

The stable path is for humans and downstream local usage.
The history path is for provenance and reproducibility.

## Rendered artifacts

Rendered artifacts behave differently.

`linkar render ...` inside a project writes directly to the visible project path, for example:

```text
study/
  demultiplex/
    run.sh
    samplesheet.csv
    .linkar/
```

That artifact is intentionally editable and runnable on its own.
When render happens inside a project, Linkar also records that artifact in `project.yaml` with
`state: rendered`.

That means the project ledger can now track:

- prepared but not yet executed rendered bundles
- managed executed runs
- adopted historical runs imported from elsewhere

The `adopted` flag is provenance, not lifecycle. Use `state` for lifecycle and `adopted: true`
only when the run was imported into the project index after the fact.

## `.linkar/` inside a run artifact

The `.linkar/` directory is Linkar’s metadata folder for that artifact.

Important files:

- `meta.json`
- `runtime.json`

`meta.json` stores:

- template id/version
- instance id
- resolved params
- param provenance
- declared outputs
- collected outputs
- pack and binding info
- warnings
- command
- lifecycle state

`runtime.json` stores:

- command
- cwd
- return code
- success
- timestamps
- captured stdout
- captured stderr
- warnings

User-facing outputs belong under `results/`, not under `.linkar/`.

## Adopting existing runs

If you already have an ad hoc Linkar run, you can adopt it into a project:

```bash
linkar project init --name study --adopt /path/to/run
linkar project adopt-run /path/to/run
```

Adoption requires real Linkar metadata. It is not a generic import of arbitrary folders.

Before adoption, Linkar refreshes outputs through the declared output contract so imported metadata
matches the declared output contract.

Adopted runs keep `adopted: true` and also receive a lifecycle `state`, usually `completed`,
`failed`, or `rendered`, inferred from their recorded metadata.

## Collecting outputs after manual execution

If you run a rendered `run.sh` directly, use:

```bash
linkar collect /path/to/rendered_dir
```

This updates:

- `.linkar/meta.json`
- `project.yaml` outputs when the artifact belongs to a project

`collect` refreshes declared outputs for a registered run. It does not create an unrelated project
entry from scratch; registration happens during `render`, `run`, or explicit adoption.

## Removing runs from a project

Project run removal is first-class:

```bash
linkar project remove-run fastqc_001
linkar project remove-run fastqc --delete-files
```

Behavior:

- accepts `instance_id`
- accepts a unique template id if it is unambiguous in the project
- accepts a run path or meta path
- `--delete-files` also removes the recorded run directory from disk

If a template id matches multiple recorded runs, Linkar returns an ambiguity error instead of
guessing.
