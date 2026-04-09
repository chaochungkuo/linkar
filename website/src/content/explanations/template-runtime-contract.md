---
title: Template runtime contract
description: The `linkar_template.yaml` contract, `run.command` versus `run.sh`, and what render and run do.
order: 3
---

Linkar templates are small runtime contracts, not mini workflow languages.

The canonical template file is `linkar_template.yaml`. Linkar still accepts `template.yaml` for
backward compatibility, but new templates should use the canonical name.

## Template shape

The smallest useful template is usually:

```yaml
id: simple_echo
version: 0.1.0
description: Write one greeting file.
params:
  name:
    type: str
    required: true
outputs:
  greeting_file:
    path: greeting.txt
run:
  mode: direct
  command: >-
    printf 'hello %s\n' "${param:name}" > "${LINKAR_RESULTS_DIR}/greeting.txt"
```

Top-level fields:

- `id`
- `version`
- `description`
- `params`
- `outputs`
- `tools`
- `run`

## Parameter types

Linkar supports:

- `str`
- `int`
- `float`
- `bool`
- `path`
- `list[path]`

Use explicit defaults in the schema whenever possible. That keeps wrapper logic small and makes the
CLI help clearer.

## Declared outputs

Outputs are how Linkar records what a template produced.

Common patterns:

```yaml
outputs:
  results_dir: {}
  report_html:
    path: reports/report.html
  fastq_files:
    glob: output/**/*.fastq.gz
```

Rules:

- `results_dir: {}` means the whole `results/` directory
- `path` is resolved relative to `results/`
- `glob` is also resolved relative to `results/`
- only existing outputs are recorded

## Tool requirements

Templates can declare external commands that must exist before execution:

```yaml
tools:
  required:
    - pixi
  required_any:
    - [bcl-convert, bcl_convert]
```

This is a preflight check. It is not an environment manager.

## `run.command` versus `run.sh`

Use `run.command` for a thin wrapper around one real command.

Use `run.sh` only when the template needs real local logic:

- branching
- temp files
- generated configs
- multi-step local orchestration
- traps and cleanup

`run.py` is also a good option once shell stops being clearer.

## Explicit parameter placeholders

The preferred form in `run.command` is:

```bash
"${param:bcl_dir}"
"${param:samplesheet}"
${param:run_name:+--run-name "${param:run_name}"}
```

This is clearer than relying on the older implicit shell convention where `bcl_dir` became
`BCL_DIR`.

Linkar still supports the older form because existing templates use it, but new templates should
prefer `${param:...}`.

## What `linkar render` does

`linkar render ...` stages a standalone runnable artifact and stops there.

Render behavior:

- writes one final `run.sh`
- resolves parameters into the rendered script
- localizes bound file parameters into the rendered directory when needed
- writes metadata under `.linkar/`
- does not execute the template
- does not append a project run-history entry

In a project, render defaults to the visible project path such as `./demultiplex`, not to
`.linkar/runs/...`.

## What `linkar run` does

`linkar run ...` always executes.

Run behavior:

- stages the run under `.linkar/runs/<instance_id>/`
- executes the template
- collects declared outputs
- writes `.linkar/meta.json` and `.linkar/runtime.json`
- appends a run record to `project.yaml`
- updates the stable project alias such as `./fastqc`

That split is intentional:

- `render` creates a handoff artifact
- `run` creates recorded project history

## Manual execution after render

If you manually execute a rendered `run.sh`, Linkar is not involved in the execution itself.

You can collect outputs afterward with:

```bash
linkar collect /path/to/rendered_dir
```

That updates `.linkar/meta.json` and, when the rendered artifact belongs to a project, also updates
`project.yaml`.
