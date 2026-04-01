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
- a recorded run directory
- `.linkar/meta.json` for provenance

This is the Linkar user path.

Template authoring is separate. Template repos can use `test.sh`, `test.py`, Pixi, pytest, or
other local tooling, but that is template-author workflow rather than the main Linkar runtime path.
