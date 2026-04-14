---
title: Python entrypoints, shell wrappers, and runtime metadata
description: A practical pattern for templates that outgrow shell while still rendering a readable `run.sh` and recording the real runtime command.
order: 9
status: ready
---

Once a template grows beyond a thin launcher, the cleanest pattern is usually:

```text
my_template/
  linkar_template.yaml
  run.sh
  run.py
  test.py
  optional config templates...
```

Use each file for one job:

- `linkar_template.yaml` is the runtime contract
- `run.sh` is a thin human-facing entrypoint
- `run.py` holds the real execution logic
- `test.py` exercises the runtime locally without depending on `linkar run`

This keeps rendered bundles easy to inspect while moving branching, config generation, and command
assembly into Python where they are easier to test.

## When this pattern is a good fit

Prefer `run.py` plus a thin `run.sh` when the template needs:

- nontrivial parameter handling
- generated config files
- structured runtime metadata
- command assembly with optional flags
- cleanup logic
- direct local tests with mocked executables

If one shell command is enough, stay with `run.command`.

If a few shell lines are enough, use `run.sh`.

Switch to `run.py` when shell stops being clearer.

## Recommended contract

Example:

```yaml
id: nfcore_methylseq
version: 0.1.0
description: RRBS-first nf-core/methylseq wrapper.
tools:
  required:
    - pixi
    - python3
    - docker
params:
  samplesheet:
    type: path
    required: true
  genome:
    type: str
    required: true
  rrbs:
    type: bool
    default: true
outputs:
  results_dir: {}
  software_versions:
    path: software_versions.json
  runtime_command:
    path: runtime_command.json
run:
  mode: render
  entry: run.sh
```

## Keep `run.sh` thin

`run.sh` should stay readable:

```bash
#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "${script_dir}/run.py"
```

That gives humans one obvious file to execute after `linkar render ...`:

```bash
bash run.sh
```

while keeping the real logic out of shell.

## Put the real logic in `run.py`

Typical responsibilities for `run.py`:

- read required and optional environment variables
- validate resolved parameters
- generate runtime config files
- construct the final tool command as a list
- write `software_versions.json`
- write `runtime_command.json`
- execute the final command
- perform cleanup that belongs to the template

Example command assembly:

```python
cmd = [
    "pixi",
    "run",
    "nextflow",
    "run",
    "nf-core/methylseq",
    "-r",
    "4.2.0",
    "-profile",
    "docker",
    "-c",
    str(runtime_config),
    "--input",
    samplesheet,
    "--outdir",
    str(results_dir),
    "--genome",
    genome,
    "--multiqc_title",
    project_title,
]
if rrbs:
    cmd.append("--rrbs")
```

This is easier to maintain and test than complex shell quoting.

## Record runtime metadata explicitly

Do not make downstream tools parse `run.sh` or `run.py` unless they have to.

Instead, write explicit runtime metadata artifacts.

Recommended pair:

- `software_versions.json`
- `runtime_command.json`

Keep them separate:

- `software_versions.json` answers which tools and versions were used
- `runtime_command.json` answers how this specific run was executed

Example `runtime_command.json`:

```json
{
  "template": "nfcore_methylseq",
  "engine": "nextflow",
  "pipeline": "nf-core/methylseq",
  "pipeline_version": "4.2.0",
  "command": [
    "pixi",
    "run",
    "nextflow",
    "run",
    "nf-core/methylseq",
    "-r",
    "4.2.0"
  ],
  "command_pretty": "pixi run nextflow run nf-core/methylseq -r 4.2.0",
  "params": {
    "genome": "GRCh38",
    "rrbs": true
  },
  "artifacts": {
    "nextflow_config": "/abs/path/results/nextflow.config",
    "software_versions": "/abs/path/results/software_versions.json"
  }
}
```

This is much more stable than trying to reconstruct runtime behavior from source files later.

## Recommended local test flow

Template-local tests should not require Linkar to execute the template.

A good `test.py` usually:

- prepares a temporary directory
- creates fake `pixi`, `nextflow`, or other external commands on `PATH`
- sets the environment variables that `run.py` expects
- runs `python3 run.py`
- inspects generated files and recorded metadata

Typical assertions:

- the final command contains the expected flags
- generated config files do not contain unresolved placeholders
- `runtime_command.json` records the final command and params
- `software_versions.json` is written

This keeps runtime logic testable even when Linkar is not available in the test environment.

## Rule of thumb

- use `run.command` when one command is enough
- use `run.sh` when shell is still the clearest implementation
- use `run.py` when the template starts generating files, branching heavily, or recording runtime metadata
- keep `run.sh` as a thin wrapper when you still want rendered bundles to have one obvious entrypoint
