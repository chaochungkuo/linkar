---
title: Getting started with a local project
description: Create a project, add a pack, run your first template, and inspect the result.
order: 1
status: ready
---

Start with the shortest useful flow:

```bash
linkar project init --name study
cd study
linkar pack add ~/github/izkf_genomics_pack --id izkf
linkar run fastqc --input sample.fastq.gz
linkar inspect run fastqc_001
```

This gives you:

- a normal project directory
- `project.yaml`
- a stable project-root directory such as `./fastqc`
- immutable run history under `.linkar/runs/`
- `.linkar/runs/<instance_id>/.linkar/meta.json` for provenance

## What happens after `linkar run`

In project mode, Linkar now separates:

- the stable project-facing alias, such as `./fastqc`
- the immutable recorded run under `.linkar/runs/fastqc_001`

That means the project root stays readable while the real history remains preserved.

## Typical next commands

```bash
linkar project runs
linkar inspect run fastqc_001
linkar templates
```

Use `linkar project runs` to review what happened locally, and `linkar inspect run` to read the
metadata and outputs for one recorded run.

This is the Linkar user path.

Template authoring is separate. Template repos can use `test.sh`, `test.py`, Pixi, pytest, or
other local tooling, but that is template-author workflow rather than the main Linkar runtime path.
