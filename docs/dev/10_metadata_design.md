# Metadata Design

This document defines the purpose and shape of Linkar run metadata.

Metadata is one of the core value propositions of Linkar. A run is not complete if it only produces output files without also leaving behind a structured explanation of what happened.

## Goals
Metadata should be:

- human-readable
- machine-readable
- useful for reproducibility
- useful for project inspection
- useful for AI reasoning
- sufficient for later methods generation

## Location
Run metadata lives at:

```text
outdir/.linkar/meta.json
```

This keeps metadata colocated with the run artifact.

## Relationship to `runtime.json`
`meta.json` is the structured semantic record of the run.
`runtime.json` is the execution log and runtime detail record.

Both are useful, but they serve different purposes.

## Minimum Fields
At minimum, `meta.json` should capture:

- `template`
- `instance_id`
- `params`
- `param_provenance`
- `outputs`
- `software`
- `pack` when applicable
- `binding` when applicable
- `command`
- `timestamp`
- `run_mode`

## Field Semantics
### `template`
The template definition id used for the run.

Example:

```json
"template": "fastqc"
```

### `instance_id`
The concrete run identifier.

Example:

```json
"instance_id": "fastqc_001"
```

### `params`
The resolved parameter values actually used for execution.

These should be post-resolution values, not partial inputs.

### `param_provenance`
The origin of each resolved parameter value.

Typical provenance sources include:

- `explicit`
- `binding`
- `project`
- `default`

This field is important because it explains not just what value was used, but why that value was selected.

### `outputs`
The outputs intentionally exposed by the run for downstream use.

This is the key bridge between execution and chaining.

When a template declares outputs, Linkar resolves those names against the run directory and records the ones that exist after execution. For most templates this means named paths under `results/`, with optional per-output `path` overrides in `linkar_template.yaml`.
Collection-style outputs declared with `glob` are recorded as lists of matched paths rather than single strings.

### `software`
Software/version information relevant to reproducibility.

This may include:

- Linkar version
- template-specific tool versions
- environment identifiers in future versions

### `pack`
The selected pack reference when the template was loaded from a pack.

In early versions this may be a local path. Later versions may include richer asset identity such as Git revision or registry reference.

### `binding`
The selected binding reference when a binding was used.

This may be:

- `default`
- a local path
- a richer remote or registry reference in later versions

### `command`
The executed command or entrypoint description.

This should help a later reader understand what was invoked.

### `timestamp`
The execution completion time or another clearly defined run timestamp.

The timestamp format should be stable and machine-readable.

### `run_mode`
The Linkar action used to produce the artifact.

Current values are:

- `run`
- `render`

## Recommended Additional Fields
Future versions may include fields such as:

- parameter provenance
- pack identity/version
- environment snapshot
- host/platform details
- references to methods-generation data

These additions should preserve the file's readability and stability.

## Example
Example shape:

```json
{
  "template": "fastqc",
  "instance_id": "fastqc_001",
  "params": {
    "fastq_dir": "./bclconvert_001/results/fastq"
  },
  "param_provenance": {
    "fastq_dir": {
      "source": "project",
      "key": "fastq_dir"
    }
  },
  "outputs": {
    "report_dir": "./results"
  },
  "software": [
    {"name": "linkar", "version": "0.1.0"},
    {"name": "fastqc", "version": "0.12.1"}
  ],
  "pack": {
    "ref": "/opt/linkar/packs/genomics-pack"
  },
  "binding": null,
  "command": ["run.sh"],
  "timestamp": "2026-03-26T15:30:00Z",
  "run_mode": "run"
}
```

In project mode, the project index may point `path` at a stable project-root alias such as `./fastqc`, while `meta.json` itself continues to live inside the immutable history directory under `.linkar/runs/fastqc_001/`.

## Design Principles
Metadata should be:

- structured rather than narrative
- explicit rather than inferred
- stable enough for tooling to parse safely
- concise enough to inspect without specialized software

## Relationship to Project State
`project.yaml` should index runs.
`meta.json` should explain runs in detail.

The project file should not absorb all metadata fields, because that would make project state bloated and fragile.

## LLM and Agent Use
Metadata should be easy for AI systems to inspect.

This implies:

- predictable paths
- stable keys
- clear parameter and output naming
- explicit parameter provenance
- minimal ambiguous free text

AI-readability should come from structure, not from trying to make metadata conversational.

## Summary
`meta.json` should be the durable semantic record of a Linkar run:

- colocated with the artifact
- structured for tooling
- rich enough for reproducibility
- small enough to inspect quickly
