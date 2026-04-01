# Project Specification

This document defines the structure and role of a Linkar project.

A project is the local state container that records template instances over time and makes their outputs available for later runs. It is intentionally lightweight: a project is an index of run history, not a workflow definition or scheduler.

## Purpose
A Linkar project exists to provide:

- A stable execution context
- A simple index of prior runs
- A way to support lightweight chaining through outputs
- A human-readable and AI-readable record of project history

The project should help users answer:

- What has already been run here?
- Which outputs are available?
- Where is the metadata for a past run?
- What should a later template consume by default?

## Project Root
A project is represented by a normal filesystem directory containing a `project.yaml` file.

Example:

```text
study/
  project.yaml
  fastqc/
  rnaseq/
  .linkar/
    runs/
      fastqc_001/
      rnaseq_001/
```

The presence of `project.yaml` marks the directory as a Linkar project.

## Project Discovery
For normal CLI usage, Linkar should assume the current working directory is the first project candidate.

Default behavior:

- Look for `project.yaml` in the current directory
- If found, use it as the active project
- If not found, the run may proceed in ephemeral mode when allowed

Explicit project paths may still be supported, but they should not be required for the common interactive path.

## `project.yaml`
The canonical project state file is `project.yaml`.

Current minimal example:

```yaml
id: project_001
packs: []
templates:
  - id: fastqc
    template_version: 0.1.0
    instance_id: fastqc_001
    path: ./fastqc
    history_path: ./.linkar/runs/fastqc_001
    params: {}
    outputs:
      fastq_dir: ./fastqc/results
    meta: ./.linkar/runs/fastqc_001/.linkar/meta.json
```

## Top-Level Fields
### `id`
Required.

This is the stable identifier of the project.

Rules:

- Should be human-readable
- Should remain stable over time
- Does not need to encode filesystem location

### `templates`
Required.

This is the ordered list of template instances recorded in the project.

Ordering matters because later resolution logic may use the most recent matching output when selecting defaults.

### `packs`
Optional in the earliest versions, but likely to become a standard project field.

This lists the packs that the project makes available for template discovery.

This field is specifically project-scoped. It should not be confused with ad hoc pack selection on a single command invocation.

To keep implementation simple and explicit, each pack entry should be able to declare:

- the pack reference
- the binding choice for that pack, if any

Pack references should be loadable in a symmetric way, typically by:

- local path
- Git or GitHub URL
- future registry reference

Example:

```yaml
packs:
  - ref: github:org/genomics-pack
    binding: default
  - ref: github:facility/private-pack
```

The recommended meanings are:

- `binding: default` means "use the pack's default binding"
- omit `binding` to mean "no binding selected"
- use another reference to mean "override the pack default with this binding asset"

This avoids a separate ambiguous top-level binding list and makes binding choice reproducible.

Pack and binding references may later resolve through Linkar's asset cache, but the project file should continue to record the original asset reference rather than an internal cache path.

If Linkar later supports user/global pack configuration, that layer should remain secondary to the project file. The project file is the reproducible source of truth for repeated work in a specific project.

## Template Instance Record
Each item in `templates` represents one recorded template instance.

Expected fields:

- `id`
- `template_version`
- `instance_id`
- `path`
- `history_path`
- `params`
- `outputs`
- `meta`

### `id`
The template definition id, such as `fastqc` or `rnaseq`.

### `instance_id`
The unique identifier for this run within the project.

Examples:

- `fastqc_001`
- `fastqc_002`

### `template_version`
The template definition version used for this run, if the template declares one.

This is provenance only. It should help later inspection and reproducibility, but it should not be treated as the primary lookup key for template resolution.

### `path`
The relative path from the project root to the stable user-facing directory for the template.

In project mode this is typically a stable alias such as `./fastqc` or `./multiqc`.

### `history_path`
The relative path from the project root to the immutable recorded run artifact.

Typical value:

```text
./.linkar/runs/fastqc_001
```

### `params`
The resolved parameters used for that run.

These are recorded for inspection and provenance. They are not a substitute for the full metadata record, but they make project state easier to scan.

### `outputs`
The named outputs exposed by that run for later use.

These should be the values that downstream resolution logic can consume.

Examples:

```yaml
outputs:
  fastq_dir: ./bclconvert/results/fastq
  report_html: ./fastqc/results/report.html
```

### `meta`
The relative path from the project root to the run metadata file, typically:

```text
./.linkar/runs/fastqc_001/.linkar/meta.json
```

This provides a bridge from project-level indexing to the full run record.

## Responsibilities of the Project
The project layer is responsible for:

- Recording template instances
- Preserving instance order
- Indexing outputs for future resolution
- Linking each instance to its metadata record
- Recording active packs and per-pack binding choices when project-level asset configuration is used
- Providing a stable local context for repeated runs

The project layer is not responsible for:

- Defining a full workflow graph
- Scheduling execution
- Replacing per-run metadata
- Managing runtime environments

## Relationship to Run Directories
Each template instance should have its own run directory.

A common layout is:

```text
study/
  project.yaml
  bclconvert/
  fastqc/
  .linkar/
    runs/
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

The project root stays readable, while immutable run history lives under `.linkar/runs/`.

This is important:

- The project is the index
- The stable project-root directory is the current user-facing path
- The history run directory is the immutable artifact

## Relative Path Rules
Paths recorded in `project.yaml` should generally be relative to the project root.

This improves:

- Portability
- Readability
- Project relocation

Absolute paths may still appear in runtime metadata where necessary, but the project index should prefer relative references whenever possible.

## Chaining Behavior
Projects enable lightweight chaining by exposing prior outputs to later resolution steps.

Typical behavior:

1. A template instance records outputs in project state.
2. A later template requests a parameter such as `fastq_dir`.
3. Resolution logic searches project history for the most recent compatible output.
4. That value is used unless a higher-precedence source overrides it.

This allows multi-step work without requiring explicit workflow graph construction.

## Ordering and History
The `templates` list should be append-only in the common case.

This gives the project a simple historical model:

- earlier runs remain visible
- later runs can override earlier outputs through recency
- project history stays inspectable

The project should behave like an execution log with indexed outputs, not like mutable workflow state that constantly rewrites its own past.

## Project Initialization
Creating a project should produce a minimal `project.yaml`.

Example:

```yaml
id: study
packs: []
templates: []
```

Initialization should be lightweight and should not require additional services or generated infrastructure.

## Ephemeral Execution
If no project is active, Linkar may still execute a template in ephemeral mode.

In that case:

- A run directory is still created
- Metadata is still written
- Project-level chaining is not available
- Minimal tracking occurs under `.linkar/runs/`

This preserves quick execution without weakening the project model.

## Validation Rules
The core should validate at least the following:

- `project.yaml` exists when a project is expected
- Top-level structure is a mapping
- `id` exists
- `templates` exists and is a list
- Each template instance record has the required fields
- Recorded paths are structurally valid

Validation should favor early, clear errors over silent recovery.

## Portability and Transparency
The project format should remain:

- File-based
- Human-readable
- Easy to inspect in version control if desired
- Stable enough for AI and UI tooling to consume

This is why `project.yaml` should remain small. Large or highly dynamic state should live in run artifacts, not be endlessly accumulated into complex project internals.

## Non-Goals
The project specification should explicitly avoid:

- Encoding a full DAG
- Embedding runtime logs directly in `project.yaml`
- Storing every possible derived detail from a run
- Acting as a hidden database behind the filesystem
- Replacing `meta.json` as the detailed provenance source

If the project file becomes too rich, it will become brittle and hard to reason about.

## Example
Example project:

```yaml
id: study
packs:
  - ref: github:org/genomics-pack
    binding: default
templates:
  - id: bclconvert
    instance_id: bclconvert_001
    path: ./bclconvert
    history_path: ./.linkar/runs/bclconvert_001
    params:
      bcl_dir: /data/run42
      threads: 8
    outputs:
      fastq_dir: ./bclconvert/results/fastq
    meta: ./.linkar/runs/bclconvert_001/.linkar/meta.json
  - id: fastqc
    instance_id: fastqc_001
    path: ./fastqc
    history_path: ./.linkar/runs/fastqc_001
    params:
      fastq_dir: ./bclconvert/results/fastq
    outputs:
      report_dir: ./fastqc/results
    meta: ./.linkar/runs/fastqc_001/.linkar/meta.json
```

## Summary
A Linkar project should remain a small and transparent state index:

- identified by `project.yaml`
- discovered from the current directory by default
- optionally recording active packs and per-pack binding choices
- storing an ordered record of template instances
- indexing outputs and metadata for later reuse
- supporting chaining without becoming a workflow engine

If the project stays this simple, it will remain useful as shared context rather than becoming a second, more fragile execution layer.
