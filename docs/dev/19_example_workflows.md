# Example Workflows

This document gives concrete examples of how Linkar should feel in practice.

The goal is not to define workflow syntax. The goal is to show how small, composable template runs can be chained through project context.

## Example 1: RNA-seq
Conceptual chain:

```text
bclconvert -> fastqc -> rnaseq
```

Example session:

```bash
mkdir study && cd study
linkar project init .
linkar run bclconvert --param bcl_dir=/data/run42
linkar run fastqc
linkar run rnaseq
```

Expected behavior:

- `bclconvert` exposes `fastq_dir`
- `fastqc` can consume `fastq_dir` from project history
- `rnaseq` can consume the latest relevant `fastq_dir` unless overridden

## Example 2: Quick One-Off Run

```bash
mkdir scratch && cd scratch
linkar run fastqc --param fastq_dir=/data/test_fastq
```

Expected behavior:

- no `project.yaml` is required
- Linkar runs in ephemeral mode
- outputs and metadata are written under `.linkar/runs/`

## Example 3: Explicit Override

```bash
cd study
linkar run rnaseq --param fastq_dir=/alt/input/fastq
```

Expected behavior:

- explicit caller input overrides project-derived fallback
- the final resolved parameter is recorded in metadata

## Example 4: Repeat Run

```bash
cd study
linkar run fastqc
linkar run fastqc
```

Expected behavior:

- two distinct instances are created
- the stable project-root path still stays `./fastqc`
- project history preserves both
- later resolution can still use recency where appropriate

## Summary
These examples show the intended operating style:

- project mode for normal chained work
- ephemeral mode for quick runs
- explicit input overriding implicit reuse
- repeated runs remaining visible as first-class history
