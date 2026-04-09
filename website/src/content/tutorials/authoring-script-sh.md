---
title: Authoring a Template Runtime
description: Use run.command for thin wrappers and run.sh only when the template needs real script logic.
order: 4
status: ready
---

Linkar templates should stay small enough to read in one sitting.

The default decision is:

- use `run.command` for a thin one-command wrapper
- use `run.sh` when the template needs real shell logic

## Start with the smallest useful contract

The smallest useful template is often just `linkar_template.yaml` plus a local test:

```text
my_template/
  linkar_template.yaml
  test.py
```

Example:

```yaml
id: simple_echo
version: 0.1.0
description: Write a greeting file.
params:
  name:
    type: str
    required: true
outputs:
  greeting_file:
    path: greeting_file
run:
  command: >-
    printf 'hello %s\n' "${param:name}" > "${LINKAR_RESULTS_DIR}/greeting_file"
```

That is cleaner than creating a `run.sh` whose only job is to forward one command.

## How parameters arrive in `run.command` and `run.sh`

The preferred authoring style in `run.command` is the explicit placeholder form.

If the template declares:

```yaml
params:
  input_fastq:
    type: path
    required: true
  threads:
    type: int
    default: 4
```

then a command should normally read:

- `${param:input_fastq}`
- `${param:threads}`

Linkar still supports the older implicit shell-variable convention:

- `input_fastq` -> `${INPUT_FASTQ}`
- `threads` -> `${THREADS}`

but new templates should prefer `${param:...}` because it is clearer to template authors.

Use explicit defaults in the schema whenever possible. That keeps runtime logic small and readable.

## When `run.sh` is the better tool

Use `run.sh` when the template needs:

- branching
- temp files
- generated config files
- multiple local commands
- traps and cleanup

Typical shape:

```text
my_template/
  linkar_template.yaml
  run.sh
  test.sh   or   test.py
  optional support files...
```

Example:

```yaml
run:
  entry: run.sh
```

```bash
#!/usr/bin/env bash
set -euo pipefail

if [[ "${PAIRED_END:-true}" == "true" ]]; then
  mytool --r1 "${R1}" --r2 "${R2}" --out "${LINKAR_RESULTS_DIR}"
else
  mytool --r1 "${R1}" --out "${LINKAR_RESULTS_DIR}"
fi
```

## Render command and launcher generation

`linkar render ...` stages the template bundle and writes one standalone `run.sh` without executing the template.

The rendered script does not silently `cd` for you. It expects to be run from inside the rendered directory, so the artifact stays explicit and easy to inspect.

That is especially useful for templates declared as one command:

```yaml
run:
  command: >-
    pixi run python -m demux_pipeline.cli
    --outdir "${LINKAR_RESULTS_DIR}"
    --bcl_dir "${param:bcl_dir}"
    --samplesheet "${param:samplesheet}"
```

The rendered directory then contains one launcher, not a template-local wrapper plus a second outer
wrapper.

## Keep testing local and simple

Use one local test entrypoint:

- `test.sh` for script-oriented templates
- `test.py` for contract inspection, filesystem assertions, and more involved mocking

Normal validation path:

```bash
linkar test simple_echo --pack ./examples/packs/basic
```

## Rule of thumb

- prefer `run.command` when one command is enough
- prefer `run.sh` when logic is real and local
- switch to `run.py` when shell stops being clearer
