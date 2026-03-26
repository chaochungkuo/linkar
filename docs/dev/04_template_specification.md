# Template Specification

This document defines the contract for a Linkar template.

A template is the unit of reusable execution in Linkar. The purpose of the template specification is to keep that unit simple, portable, and easy for both humans and the core engine to understand.

## Design Goals
A valid template should be:

- Easy to author
- Easy to inspect from the filesystem
- Runnable without hidden framework behavior
- Explicit about parameters
- Stable enough to be reused across projects

The template format should remain deliberately small. If template behavior becomes too rich, Linkar risks turning into a workflow language rather than a template runner.

## Template Directory
A template is represented as a directory.

Minimum expected structure:

```text
my_template/
  template.yaml
  run.sh
```

Other supporting files may also exist:

```text
my_template/
  template.yaml
  run.sh
  scripts/
  assets/
  README.md
```

The key point is that the template should remain understandable as a normal directory, not a generated or opaque bundle.

## Required Files
### `template.yaml`
This file defines the template interface and execution settings.

It is required.

### Run Entrypoint
The template must define a runnable entrypoint in `template.yaml`.

Typical examples:

- `run.sh`
- `run.py`
- `bin/execute`

The entrypoint path is relative to the template root.

## `template.yaml` Structure
The current minimal structure is:

```yaml
id: bclconvert_qc
params:
  bcl_dir:
    type: path
    required: true
  threads:
    type: int
    default: 8
run:
  entry: run.sh
  mode: direct
```

## Top-Level Fields
### `id`
Required.

This is the stable identifier of the template definition.

Rules:

- Must be unique within a pack
- Should be short and human-readable
- Should remain stable over time
- Should not encode instance-specific information

Examples:

- `bclconvert`
- `fastqc`
- `rnaseq`

### `params`
Optional, but usually expected.

This defines the parameter schema for the template. Each parameter is declared by name and associated with a small spec.

If omitted, the template takes no declared parameters.

### `run`
Required.

This defines how the template should be executed.

Current expected fields:

- `entry`: relative path to the executable entrypoint
- `mode`: execution mode, typically `direct`

## Parameter Specification
Each parameter entry may define:

- `type`
- `required`
- `default`

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

### Parameter Types
The current supported types are:

- `str`
- `int`
- `float`
- `bool`
- `path`

If omitted, `type` defaults to `str`.

### Required Parameters
If `required: true`, the parameter must resolve successfully before execution.

Resolution may come from:

- Explicit CLI input
- Binding or function logic
- Project outputs
- A default value

If a required parameter cannot be resolved, the run should fail before execution begins.

### Default Values
If `default` is present, it is used only if no higher-precedence source provides a value.

Defaults should be simple and explicit. Template authors should avoid using defaults to hide major execution assumptions.

## Execution Contract
The template entrypoint is the actual program Linkar will run.

The entrypoint should behave like a normal standalone script or executable. Linkar is responsible for orchestration around the run, but the template owns the execution logic itself.

This means:

- The core resolves parameters
- The core prepares the output directory
- The core passes execution context into the environment
- The template performs the domain-specific work

## Execution Modes
### `direct`
In `direct` mode, Linkar executes the entrypoint directly.

This should be the common and default mode.

### `render`
`render` may exist in future versions for cases where Linkar first renders an execution artifact before running.

It should remain optional and should not complicate the common template authoring path.

## Parameter Transport
Resolved parameters are passed to the template through environment variables.

The transport rule is:

- Parameter names are converted to upper snake case
- Values are serialized as strings

Examples:

- `fastq_dir` -> `FASTQ_DIR`
- `threads` -> `THREADS`
- `paired_end` -> `PAIRED_END`

Example environment:

```text
FASTQ_DIR=/data/reads
THREADS=8
PAIRED_END=true
```

This transport mechanism is intentionally simple and language-agnostic.

## Linkar Runtime Environment
In addition to parameter variables, the core should expose runtime context variables to the template.

Expected examples include:

- `LINKAR_OUTPUT_DIR`
- `LINKAR_RESULTS_DIR`
- `LINKAR_INSTANCE_ID`
- `LINKAR_PROJECT_DIR` when a project is active

These variables let the template interact with the run context without hardcoding project-specific paths.

## Output Expectations
The output directory is also the execution directory.

Expected layout:

```text
outdir/
  results/
  .linkar/
    meta.json
    runtime.json
```

The template should write its user-facing outputs into `results/` or clearly defined subpaths under the output directory.

The template should not write metadata files that duplicate or conflict with the Linkar-managed `.linkar/` records.

## Authoring Rules
Template authors should follow these rules:

- The run entrypoint must be executable in a normal shell or interpreter context.
- The template should not assume a specific project path layout beyond the provided environment variables.
- The template should treat resolved parameters as the full execution contract.
- The template should produce deterministic outputs as far as practical for the same inputs and environment.
- The template should avoid hidden side effects outside the output directory unless explicitly required.

## Validation Rules
The core should validate at least the following before execution:

- `template.yaml` exists
- `id` exists
- `run.entry` exists
- The referenced entrypoint exists
- Declared parameter specs are structurally valid
- The execution mode is supported

The goal of validation is to fail early and clearly before any domain-specific work begins.

## Portability Rules
Templates should be portable across:

- Different projects
- Different machines with compatible runtime environments
- Different Linkar interfaces such as CLI or API

To preserve portability:

- Template logic should stay inside the template directory or declared runtime environment
- Template behavior should not rely on the caller remembering undocumented setup steps
- Inputs should come through declared params, not ambient assumptions

## Recommended Conventions
These conventions are not all mandatory, but they should be encouraged:

- Include a small `README.md` for non-trivial templates
- Keep parameter names stable and descriptive
- Use `path` type for filesystem inputs
- Prefer explicit output paths under `results/`
- Keep entrypoints short and delegate complex logic into supporting scripts if needed

## Example
Example template:

```text
bclconvert/
  template.yaml
  run.sh
```

```yaml
id: bclconvert
params:
  bcl_dir:
    type: path
    required: true
  threads:
    type: int
    default: 8
run:
  entry: run.sh
  mode: direct
```

```bash
#!/usr/bin/env bash
set -euo pipefail

bcl-convert \
  --input-dir "${BCL_DIR}" \
  --output-directory "${LINKAR_RESULTS_DIR}" \
  --bcl-num-conversion-threads "${THREADS}"
```

## Summary
A Linkar template should remain a small, explicit execution unit:

- defined by `template.yaml`
- run through a normal entrypoint
- configured through declared parameters
- executed inside a prepared output directory
- portable across projects

If templates remain this simple, Linkar can stay understandable while still supporting reusable, composable analyses.
