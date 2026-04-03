---
title: Getting started with a local project
description: Create a project, add a pack, run your first template, and inspect the result.
order: 1
status: ready
---

Install Linkar as a CLI tool first.

Recommended:

```bash
pipx install git+https://github.com/jovesus/linkar.git
```

Alternative for `uv` users:

```bash
uv tool install git+https://github.com/jovesus/linkar.git
```

These are user-facing install paths. Template-local Pixi environments and editable installs belong
to template authoring or Linkar repo development, not to normal Linkar usage.

## First run

Start with the shortest useful flow:

```bash
linkar config author set --name "Your Name" --email "you@example.org" --organization "IZKF"
linkar project init --name study
cd study
linkar pack add ~/github/izkf_genomics_pack --id izkf
linkar run fastqc --input sample.fastq.gz
linkar inspect run fastqc_001
```

This gives you:

- a normal project directory
- `project.yaml`
- reused author metadata from your global Linkar config
- a stable project-root directory such as `./fastqc`
- immutable run history under `.linkar/runs/`
- `.linkar/runs/<instance_id>/.linkar/meta.json` for provenance
- the option to render a standalone artifact with `linkar render ...`

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

If you started with an ad hoc run before creating a project, you can adopt it when initializing the
project:

```bash
linkar project init --name study --adopt /path/to/existing_run
```

If you want a standalone runnable artifact instead of an executed run:

```bash
linkar render simple_echo --pack ./examples/packs/basic --param name=Linkar
cd simple_echo
bash run.sh
linkar collect .
```

This is the Linkar user path.

Template authoring is separate. Template repos can use `test.sh`, `test.py`, Pixi, pytest, or
other local tooling, but that is template-author workflow rather than the main Linkar runtime path.
