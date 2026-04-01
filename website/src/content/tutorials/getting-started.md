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
linkar config pack add ~/github/izkf_genomics_pack
linkar run fastqc --input sample.fastq.gz
```

This gives you:

- a normal project directory
- `project.yaml`
- a recorded run directory
- `.linkar/meta.json` for provenance

For template authoring, start with the bundled examples under `examples/packs/basic` and then move to `examples/packs/chaining`.
