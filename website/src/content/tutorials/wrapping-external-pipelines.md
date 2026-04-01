---
title: Wrapping an external pipeline
description: Turn an existing script or external repo into a Linkar template without copying all its code.
order: 4
status: ready
---

The best Linkar wrapper is usually thin.

Linkar should own:

- the runtime contract
- parameter resolution
- output exposure
- run provenance

The external tool should still own its real computational logic.

## Start with the interface, not the wrapper code

The first job is to define a stable template contract in `linkar_template.yaml`.

For example:

```yaml
id: fastqc
version: 0.1.0
description: Run FastQC on one FASTQ file.
params:
  input_fastq:
    type: path
    required: true
  threads:
    type: int
    default: 4
outputs:
  results_dir: {}
  fastqc_reports:
    glob: fastqc/*_fastqc.html
run:
  entry: run.sh
  mode: direct
```

Now the wrapper has a clear job: adapt Linkar's resolved inputs to the underlying tool.

## Thin shell wrappers are fine when the tool is already shell-first

For a normal command-line tool, `run.sh` can stay very small:

```bash
#!/usr/bin/env bash
set -euo pipefail

mkdir -p "${LINKAR_RESULTS_DIR}/fastqc"

fastqc \
  --threads "${THREADS}" \
  --outdir "${LINKAR_RESULTS_DIR}/fastqc" \
  "${INPUT_FASTQ}"
```

This is a good wrapper because:

- the contract is explicit
- the output location is deterministic
- the wrapper is easier to read than the underlying tool help text

## Use `run.py` when the wrapper starts doing real logic

If you are wrapping a Python-based pipeline or a multi-mode entrypoint, `run.py` is usually better
than pushing more conditionals into shell.

`run.py` is the right move when the wrapper must:

- validate combinations of parameters
- assemble optional arguments clearly
- call into a Python library or Python-native pipeline
- inspect files or emit structured errors

That is why a template like `demultiplex` is better as `run.py` than as a large shell adapter.

## Keep the external repo boundary clear

You have two reasonable packaging models:

### 1. Thin wrapper around an external checkout

Use this when the external repo already has its own release cycle and you do not want to bundle it
into the template.

Template job:

- define Linkar params
- call the external entrypoint
- write outputs under `LINKAR_RESULTS_DIR`

### 2. Self-contained template bundle

Use this when the template should be portable on its own and the bundled pipeline code is part of
the template distribution.

Template directory can then contain:

```text
demultiplex/
  linkar_template.yaml
  run.py
  test.py
  demux_pipeline/
  pixi.toml
  pixi.lock
```

This is often the better choice for a real reusable template repo.

## Testing strategy

Template-local testing should stay with the template repo.

Examples:

```bash
cd templates/fastqc
bash test.sh
```

```bash
cd templates/demultiplex
python test.py
```

Then validate through Linkar:

```bash
linkar test fastqc --pack /path/to/pack
linkar test demultiplex --pack /path/to/pack
```

## Good wrapper rules

- keep the Linkar contract explicit
- keep output locations deterministic
- prefer explicit defaults over hidden omission logic
- use `run.py` once shell stops being clearer
- let the external tool own the real computation

Linkar is the runtime and packaging layer, not a replacement for the external tool itself.
