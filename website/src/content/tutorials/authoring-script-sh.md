---
title: Authoring a template with run.sh
description: Keep templates small with a real run.sh and either test.sh or test.py for local validation.
order: 3
status: ready
---

Linkar templates should stay small enough to read in one sitting.

For a shell-based template, the normal shape is:

```text
my_template/
  linkar_template.yaml
  run.sh
  test.sh   or   test.py
  optional support files...
```

`run.sh` is the real runtime entrypoint. Linkar resolves parameters, stages the template runtime
bundle into the run artifact, and executes `run.sh` there.

## Start with the smallest useful contract

`linkar_template.yaml` should describe only what the runtime actually needs.

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
    path: greeting.txt
run:
  entry: run.sh
  mode: direct
```

And the runtime script can stay normal:

```bash
#!/usr/bin/env bash
set -euo pipefail

printf 'hello %s\n' "${NAME}" > greeting.txt
```

The important point is that Linkar should not own the script logic. The template does.

## How parameters arrive in `run.sh`

Linkar exposes resolved parameters as environment variables.

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

then `run.sh` can read:

```bash
"${INPUT_FASTQ}"
"${THREADS}"
```

Use explicit defaults in the schema whenever possible. That keeps shell logic small and readable.

## How outputs are found

Declared outputs are resolved from the run artifact. By default, Linkar looks under `results/`.

Examples:

- `results_dir` resolves to `results/`
- `fastqc_dir` resolves to `results/fastqc`
- `report_html` resolves to `results/report_html`

Use `path` when the output lives somewhere more specific:

```yaml
outputs:
  multiqc_report:
    path: multiqc/multiqc_report.html
```

Use `glob` when one output name should expose a collection:

```yaml
outputs:
  fastqc_reports:
    glob: fastqc/*_fastqc.html
```

Linkar records the matched paths as a list.

## How downstream templates consume collections

If a later template needs many files, declare a `list[path]` param:

```yaml
params:
  fastqc_reports:
    type: list[path]
    required: true
```

Linkar transports that list into the runtime environment as an `os.pathsep`-joined string. Shell
and Python entrypoints can both decode it predictably.

## Keep testing local and simple

Use one local test entrypoint:

- `test.sh` for shell-oriented templates
- `test.py` for Python-oriented templates

Normal validation path:

```bash
linkar test simple_echo --pack ./examples/packs/basic
```

Faster author loop while editing:

```bash
cd examples/packs/basic/templates/simple_echo
bash test.sh
```

## When to switch to `run.py`

Use `run.sh` by default for shell-oriented templates.

Switch to `run.py` when:

- argument assembly becomes hard to read in shell
- validation logic is non-trivial
- the wrapped tool is already Python-native
- file inspection and structured errors matter

The goal is not to force shell. The goal is to keep the runtime entrypoint direct and readable.
