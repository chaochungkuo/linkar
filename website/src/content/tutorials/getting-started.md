---
title: Getting started with a local project
description: Install a GitHub pack, create a project, run your first template, and inspect the result.
order: 1
status: ready
---

This tutorial is the normal human starting path.

You have a shared pack on GitHub. You want to install it once, create a local project, run one
template, and inspect the result without learning the whole internals first.

Install Linkar as a CLI tool first.

Recommended:

```bash
pipx install git+https://github.com/chaochungkuo/linkar.git
```

Alternative for `uv` users:

```bash
uv tool install git+https://github.com/chaochungkuo/linkar.git
```

These are user-facing install paths. Template-local Pixi environments and editable installs belong
to template authoring or Linkar repo development, not to normal Linkar usage.

## First run

Start with the shortest useful flow:

```bash
linkar config pack add github:IZKF-Genomics/izkf_pack --id izkf_pack
linkar config pack list --format yaml

linkar config author set --name "Your Name" --email "you@example.org" --organization "IZKF"
linkar project init --name study
cd study

linkar run scrna_prep \
  --input-h5ad /data/study/raw_counts.h5ad \
  --organism human \
  --binding default \
  --verbose

linkar inspect run scrna_prep_001
```

This gives you:

- a normal project directory
- `project.yaml`
- a globally configured GitHub pack cached under Linkar's asset directory
- reused author metadata from your global Linkar config
- a stable project-root directory such as `./scrna_prep`
- immutable run history under `.linkar/runs/`
- `.linkar/runs/<instance_id>/.linkar/meta.json` for provenance
- recorded pack ref and resolved Git revision metadata
- the option to render a standalone artifact with `linkar render ...`

If the project-level author metadata should differ from your global defaults, update it directly in
the existing project:

```bash
linkar project author show
linkar project author set --name "Project Owner" --email "owner@example.org"
```

## What happens after `linkar run`

In project mode, Linkar now separates:

- the stable project-facing alias, such as `./scrna_prep`
- the immutable recorded run under `.linkar/runs/scrna_prep_001`

That means the project root stays readable while the real history remains preserved.

## Typical next commands

```bash
linkar project runs
linkar inspect run scrna_prep_001
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
linkar render scrna_prep \
  --pack github:IZKF-Genomics/izkf_pack \
  --input-h5ad /data/study/raw_counts.h5ad \
  --organism human \
  --binding default \
  --outdir ./scrna_prep
cd scrna_prep
bash run.sh
linkar collect .
```

This is the Linkar user path.

Template authoring is separate. If you clone the Linkar repository, the bundled `examples/packs/*`
packs are useful for learning the template contract. Template repos can use `test.sh`, `test.py`,
Pixi, pytest, or other local tooling, but that is template-author workflow rather than the main
Linkar runtime path.

Next, read [Using global packs vs project packs](../packs-and-scope/) to decide when a pack should
live in your personal config and when it should be saved into a project.
