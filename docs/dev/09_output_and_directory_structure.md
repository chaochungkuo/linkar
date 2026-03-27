# Output and Directory Structure

This document defines the filesystem layout of a Linkar run.

The output layout is part of the public contract of the system. Stable layout matters because users, templates, AI agents, and future tools all rely on predictable paths.

## Core Principle
The output directory is the execution directory.

Linkar should not separate "where the template runs" from "where the run artifact lives" unless there is a compelling future reason to do so.

This keeps the system easy to inspect and easy to move.

## Standard Layout
Each template instance should produce a directory like:

```text
outdir/
  run.sh
  results/
  .linkar/
    meta.json
    runtime.json
```

## Directory Roles
### `outdir/`
The root directory of the template instance.

This is the primary artifact for the run.

For shell-based templates, `run.sh` is the runtime entrypoint recorded with the run artifact.

In direct mode, Linkar stages the runtime bundle into this directory before execution. That staged bundle may include:

- the entrypoint
- helper scripts
- local environment files such as `pixi.toml` and `pixi.lock`
- other support files required by the runtime logic

Test-only files such as `test.sh`, `test.py`, and `testdata/` should remain in the source template directory and should not be copied into recorded run artifacts.

### `outdir/results/`
The main location for user-facing outputs produced by the template.

Examples:

- result files
- generated reports
- derived data directories

Templates should prefer writing into `results/` or clearly named subdirectories under it.

### `outdir/.linkar/`
The system-managed metadata directory.

This should contain artifacts produced by the core, not arbitrary template outputs.

Typical contents:

- `meta.json`
- `runtime.json`

## `meta.json`
`meta.json` stores the structured description of the run.

It is intended for:

- provenance
- reproducibility
- project indexing
- AI inspection
- methods generation

## `runtime.json`
`runtime.json` stores runtime execution details.

It is intended for:

- debugging
- execution auditing
- post-failure inspection

It may include command, timestamps, return code, and captured output details.

## Project Mode Layout
When a project is active, instance directories should typically live under the project root.

Example:

```text
study/
  project.yaml
  bclconvert_001/
    results/
    .linkar/
      meta.json
      runtime.json
  fastqc_001/
    results/
    .linkar/
      meta.json
      runtime.json
```

## Ephemeral Mode Layout
When no project is active, Linkar may create runs under:

```text
.linkar/runs/
```

Example:

```text
workdir/
  .linkar/
    runs/
      fastqc_20260326_153000/
        results/
        .linkar/
          meta.json
          runtime.json
```

This preserves the run artifact even when no project is present.

## Path Conventions
Linkar should use:

- stable directory names
- relative paths in `project.yaml` when possible
- conventional subpaths that external tools can rely on

Templates should not invent their own metadata directory structure that conflicts with `.linkar/`.

## Output Exposure
Not every file in `results/` is automatically a named project output.

The system should distinguish between:

- files merely present in the run directory
- outputs intentionally exposed for downstream resolution

This distinction keeps downstream chaining predictable.

## Design Constraints
The directory structure should remain:

- simple enough to inspect by eye
- stable enough for automation
- local and self-contained
- free from hidden database dependence

## Summary
The Linkar run layout should provide:

- one directory per template instance
- a clear split between user outputs and system metadata
- stable paths for chaining and inspection
- portability across machines and interfaces
