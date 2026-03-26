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
- `outputs`
- `software`
- `command`
- `timestamp`

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

### `outputs`
The outputs intentionally exposed by the run for downstream use.

This is the key bridge between execution and chaining.

### `software`
Software/version information relevant to reproducibility.

This may include:

- Linkar version
- template-specific tool versions
- environment identifiers in future versions

### `command`
The executed command or entrypoint description.

This should help a later reader understand what was invoked.

### `timestamp`
The execution completion time or another clearly defined run timestamp.

The timestamp format should be stable and machine-readable.

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
  "outputs": {
    "report_dir": "./results"
  },
  "software": [
    {"name": "linkar", "version": "0.1.0"},
    {"name": "fastqc", "version": "0.12.1"}
  ],
  "command": ["run.sh"],
  "timestamp": "2026-03-26T15:30:00Z"
}
```

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
- minimal ambiguous free text

AI-readability should come from structure, not from trying to make metadata conversational.

## Summary
`meta.json` should be the durable semantic record of a Linkar run:

- colocated with the artifact
- structured for tooling
- rich enough for reproducibility
- small enough to inspect quickly
