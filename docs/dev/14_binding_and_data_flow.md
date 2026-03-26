# Binding and Data Flow

This document describes how Linkar connects outputs from earlier runs to parameters in later runs.

The goal is to support lightweight chaining without introducing a full workflow graph language.

## Binding
Binding is the process of mapping a parameter in the current run to a value derived from:

- project state
- function logic
- explicit conventions

Examples:

- `rnaseq.fastq_dir <- latest project fastq_dir`
- `align.index <- resolve_reference_genome(ctx)`

Bindings are best understood as overlays on top of templates.

They may come from:

- a pack-provided default binding
- a separately shared facility or personal binding
- project-level per-pack configuration selecting which binding to use

## Why Binding Matters
Without binding, users would need to manually restate many intermediate paths between runs.

Binding reduces that friction while keeping the model simple and inspectable.

At the same time, bindings should remain optional. A template must still be runnable as a standalone unit when explicit parameters are supplied.

## Data Flow Model
The core data flow in Linkar is:

1. A template instance produces named outputs.
2. Those outputs are recorded in metadata and indexed in the project.
3. A later template requests parameters.
4. Resolution chooses values from explicit input, binding logic, project outputs, or defaults.
5. The next template runs with those resolved values.

This is a chaining model, not a scheduler graph.

## Implicit vs Explicit Flow
Linkar should support lightweight implicit reuse through project outputs, but not at the cost of clarity.

That means:

- recency-based fallback can be convenient
- explicit binding rules are preferred when ambiguity might arise
- the system should avoid magical cross-project inference

## Default and Override Model
The future-friendly rule should be:

- a pack may ship a default binding
- a project may accept that default binding for that pack
- a project may override it with another binding for that pack
- explicit caller input still has highest precedence

This keeps packs coherent while preserving local adaptability.

## Example
Simple RNA-seq chain:

```text
bclconvert -> fastq_dir
fastqc -> report_dir
rnaseq consumes fastq_dir
```

Possible resolution path:

- `bclconvert` records `fastq_dir`
- `rnaseq` requests `fastq_dir`
- project lookup finds the latest matching output
- `rnaseq` receives that value unless the user overrides it explicitly

## Design Constraints
Binding and data flow should remain:

- local to the active project by default
- deterministic in precedence
- explicit enough to inspect later
- narrow enough to avoid becoming workflow syntax
- replaceable without changing the underlying templates

## Summary
Linkar data flow is built on:

- named outputs
- project indexing
- parameter resolution
- optional function-backed binding

This is the mechanism that gives Linkar composability without turning it into a DAG engine.
