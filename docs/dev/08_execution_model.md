# Execution Model

This document defines the lifecycle of a Linkar run.

The execution model should stay simple: resolve inputs, prepare a run directory, execute the template entrypoint, and record the result. Linkar is not trying to become a scheduler or workflow runtime.

## Execution Goal
Each run should produce:

- a concrete template instance
- a predictable output directory
- structured metadata
- enough runtime information to inspect success or failure later

## High-Level Steps
The normal execution flow is:

1. Discover execution context
2. Load template definition
3. Load project if active
4. Resolve parameters
5. Determine `instance_id`
6. Determine `output_dir`
7. Prepare execution directory
8. Execute the template entrypoint
9. Record runtime details
10. Write metadata
11. Update project state if a project is active

This sequence should be consistent across CLI and API use.

## Step Details
### 1. Discover Execution Context
The caller may provide an explicit project or output path.

If not, the common CLI behavior should be:

- look for `project.yaml` in the current directory
- use it if found
- otherwise fall back to ephemeral execution when valid

### 2. Load Template Definition
The core loads and validates the template.

Validation should happen before any domain-specific work begins.

### 3. Load Project
If a project is active, the core loads `project.yaml` and makes prior run state available for resolution and indexing.

### 4. Resolve Parameters
All declared parameters are resolved and validated before execution.

The template entrypoint should not be asked to guess missing values.

### 5. Determine `instance_id`
Each run should receive a stable instance identifier.

Typical behavior:

- within a project, increment per template
- in ephemeral mode, use a timestamped or otherwise unique identifier

### 6. Determine `output_dir`
The output directory is also the execution directory.

Typical behavior:

- project mode: create a run directory under the project root
- ephemeral mode: create a run directory under `.linkar/runs/`
- explicit `outdir`: use the caller-provided location

### 7. Prepare Execution Directory
The core prepares the run directory layout:

```text
outdir/
  results/
  .linkar/
```

The core owns this structure, not the template.

### 8. Execute the Template Entrypoint
The core executes the entrypoint using the resolved parameter environment and runtime context environment.

The template owns domain logic.
The core owns orchestration around the run.

### 9. Record Runtime Details
The core should capture runtime facts such as:

- command executed
- working directory
- start and finish timestamps
- success/failure status
- duration when practical
- return code
- stdout/stderr when appropriate

This should happen even when the run fails.

### 10. Write Metadata
After execution, the core writes structured metadata describing the run and its outputs.

Metadata is a first-class artifact of execution, not optional debug state.

### 11. Update Project State
If a project is active, the new template instance is appended to project history and its outputs become available for later chaining.

## Success and Failure
### Successful Run
A successful run should produce:

- a populated output directory
- runtime information
- metadata
- a project index entry when a project is active

### Failed Run
A failed run should still preserve:

- the created run directory when possible
- runtime details useful for debugging
- enough context to explain what was attempted

Project indexing behavior on failure should remain conservative. In early versions, failed runs should generally not be appended as normal successful template instances unless failure semantics are defined explicitly.

## Execution Modes
### `direct`
Run the template entrypoint directly.

This is the primary execution mode and should cover the common path.

### `render`
In future versions, Linkar may support `render` mode where the core first materializes an execution artifact and then runs it.

This should remain optional and must not complicate the primary direct-execution path.

## Design Constraints
The execution model should preserve the following boundaries:

- parameter resolution happens before execution
- the core prepares the run context
- the template performs the domain-specific work
- metadata is written by the core
- project state is updated only after the run lifecycle reaches a consistent post-execution point

## Summary
The Linkar execution model should remain:

- linear
- inspectable
- filesystem-centered
- consistent across interfaces
- focused on producing a portable run artifact rather than managing a workflow graph
