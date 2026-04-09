---
title: Wrapping an external pipeline
description: Turn an existing script or external repo into a Linkar template without copying all its code.
order: 5
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

Before writing wrapper code, decide three things:

- which inputs the user should provide
- which outputs Linkar should record
- where the wrapped tool should write its results under `LINKAR_RESULTS_DIR`

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
  command: >-
    fastqc --threads "${param:threads}"
    --outdir "${LINKAR_RESULTS_DIR}/fastqc"
    "${param:input_fastq}"
```

Now the wrapper has a clear job: in the simplest case, there is no separate wrapper file at all.

## Prefer `run.command` for one-command wrappers

For a normal command-line tool, a single `run.command` string is usually the cleanest option:

```yaml
run:
  command: >-
    fastqc --threads "${param:threads}"
    --outdir "${LINKAR_RESULTS_DIR}/fastqc"
    "${param:input_fastq}"
```

This is a good wrapper because:

- the contract is explicit
- the output location is deterministic
- there is no extra wrapper file to maintain

This is the right shape for wrappers around tools like:

- `fastqc`
- `samtools`
- `bcl-convert`
- `cellranger` subcommands when you only need one stable invocation

## Use `run.sh` or `run.py` when the wrapper starts doing real logic

If you are wrapping a Python-based pipeline or a multi-mode entrypoint, `run.py` is usually better
than pushing more conditionals into shell.

`run.py` is the right move when the wrapper must:

- validate combinations of parameters
- assemble optional arguments clearly
- call into a Python library or Python-native pipeline
- inspect files or emit structured errors

That is why a template like `demultiplex` is better as either a declarative `run.command` or a real
programmatic entrypoint, rather than a large shell adapter that only forwards arguments.

For Python wrappers, Linkar already supports a direct entrypoint model. The bundled
`download_test_data` example uses:

```yaml
run:
  entry: run.py
```

and the `run.py` file reads Linkar-provided environment variables such as:

- `SOURCE_URL`
- `OUTPUT_NAME`
- `LINKAR_RESULTS_DIR`

That is the current runtime model in the codebase today.

## A realistic template layout

For a thin command wrapper:

```text
fastqc/
  linkar_template.yaml
  test.sh
```

For a shell-oriented wrapper with local logic:

```text
demultiplex/
  linkar_template.yaml
  run.sh
  test.sh
  testdata/
```

For a Python-oriented wrapper:

```text
download_test_data/
  linkar_template.yaml
  run.py
  test.sh
  testdata/
```

## Keep the external repo boundary clear

You have two reasonable packaging models:

### 1. Thin wrapper around an external checkout

Use this when the external repo already has its own release cycle and you do not want to bundle it
into the template. If you do this, prefer cloning a pinned commit rather than floating `main`.

Template job:

- define Linkar params
- call the external entrypoint
- write outputs under `LINKAR_RESULTS_DIR`

Typical shape:

```text
my_pack/
  templates/
    wrapped_pipeline/
      linkar_template.yaml
      run.sh
      test.sh
```

In this model, `run.sh` is mostly an adapter that calls a pinned checkout, installed binary, or
existing environment.

### 2. Self-contained template bundle

Use this when the template should be portable on its own and the bundled pipeline code is part of
the template distribution.

Template directory can then contain:

```text
my_pack/
  templates/
    demultiplex/
      linkar_template.yaml
      run.py
      helpers/
        samplesheet.py
      assets/
        adapter_seqs.tsv
      test.py
      testdata/
```

This is still reasonable when the bundled code really is part of the distributed template contract.

Choose this model when:

- the wrapped logic is small enough to version together with the template
- portability matters more than reusing an external repo boundary
- you want `linkar render ...` to produce a self-contained handoff artifact

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

That split mirrors the current codebase:

- local `test.sh` or `test.py` keeps authoring fast
- `linkar test ...` validates the real Linkar runtime path

## Good wrapper rules

- keep the Linkar contract explicit
- keep output locations deterministic
- prefer explicit defaults over hidden omission logic
- prefer `run.command` when one command is enough
- use `run.sh` for real local shell logic
- use `run.py` once shell stops being clearer
- let the external tool own the real computation

Linkar is the runtime and packaging layer, not a replacement for the external tool itself.
