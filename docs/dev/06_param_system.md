# Parameter System

This document defines how Linkar represents template parameters.

Parameters are the main contract between the caller, the project context, and the template entrypoint. The parameter system should stay small, explicit, and language-agnostic.

## Goals
The parameter system should:

- Be simple to author in `template.yaml`
- Be easy for the core to validate
- Be easy for templates to consume
- Work across CLI, API, and future agent use
- Avoid hidden coercion rules

## Parameter Definition
Parameters are declared under `params` in `template.yaml`.

Example:

```yaml
params:
  fastq_dir:
    type: path
    required: true
  threads:
    type: int
    default: 8
  paired_end:
    type: bool
    default: true
```

Each parameter is identified by a stable name and an optional spec.

## Supported Types
The initial parameter types are:

- `str`
- `int`
- `float`
- `bool`
- `path`

If `type` is omitted, it defaults to `str`.

These types should stay intentionally small in early versions.

## Semantics by Type
### `str`
Represents free-form string input.

Use for:

- names
- labels
- generic command arguments

### `int`
Represents integer values.

Use for:

- thread counts
- limits
- discrete numeric settings

### `float`
Represents decimal numeric values.

Use for:

- thresholds
- ratios
- scoring cutoffs

### `bool`
Represents true/false flags.

Recommended accepted input forms at the interface layer:

- `true`, `false`
- `1`, `0`
- `yes`, `no`
- `on`, `off`

The core should normalize these to a stable internal boolean representation before transport.

### `path`
Represents a filesystem path.

Use for:

- input directories
- input files
- output references passed between steps

The core should normalize paths consistently so templates do not need to guess how they were provided.

## Parameter Fields
The initial parameter schema supports:

- `type`
- `required`
- `default`

Example:

```yaml
params:
  sample_sheet:
    type: path
    required: true
  threads:
    type: int
    default: 8
```

## Required Parameters
If `required: true`, the parameter must resolve before execution begins.

Resolution may come from:

- explicit caller input
- binding/function logic
- project outputs
- default values

Failure to resolve a required parameter should stop the run before the template entrypoint is invoked.

## Default Values
Defaults are fallback values, not hardcoded execution policy.

They should be used for:

- safe operational defaults
- common resource defaults
- low-risk behavior selection

They should not be used to hide critical assumptions about data sources or project context.

## Parameter Naming
Parameter names should:

- be stable over time
- be lowercase snake case
- describe the input or setting clearly
- avoid ambiguous abbreviations when possible

Good examples:

- `fastq_dir`
- `reference_fasta`
- `threads`

Less desirable examples:

- `f`
- `x1`
- `data_input_for_primary_stage`

## Internal Representation
Inside the core, parameters should be represented as typed resolved values.

This means:

- validation happens before execution
- resolution happens before execution
- transport into the template is derived from the resolved value set

The template should receive a stable execution view, not a mix of raw unresolved sources.

## Transport to Templates
Resolved parameters are passed to template entrypoints through environment variables.

Transport rules:

- parameter names are converted to upper snake case
- values are serialized as strings

Examples:

- `fastq_dir` -> `FASTQ_DIR`
- `threads` -> `THREADS`
- `paired_end` -> `PAIRED_END`

Example:

```text
FASTQ_DIR=/data/reads
THREADS=8
PAIRED_END=true
```

This keeps the template-facing contract simple across Bash, Python, and other runtimes.

## Validation Expectations
The core should validate:

- parameter names are structurally valid
- declared types are supported
- defaults are compatible with declared types
- resolved values can be coerced to the declared type

Validation should happen before template execution.

## Design Constraints
To keep the parameter system coherent:

- avoid adding many special-case types too early
- prefer explicit bindings over magical resolution behavior
- keep template-facing transport universal
- keep the schema small enough to inspect in plain YAML

## Summary
The Linkar parameter system should remain:

- small in type surface
- explicit in declaration
- validated before execution
- normalized by the core
- transported to templates through simple environment variables
