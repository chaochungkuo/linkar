---
title: Discovery layers and site packs
description: Keep Linkar generic by putting site-specific data discovery next to the pack instead of inside core runtime semantics.
order: 8
---

Linkar should know how to orchestrate reusable work.

It should not have to know your facility's storage ontology.

That means concepts like these usually do **not** belong in Linkar core:

- where projects live on one server
- where FASTQ runs are stored
- how raw sequencing runs are named
- where local reference directories are mounted

Those are site-specific facts, not universal workflow semantics.

## The boundary

A clean design usually looks like this:

- Linkar core handles projects, templates, bindings, runs, resolve, render, run, and inspect
- a site pack holds reusable workflows and site-specific helper logic
- an agent combines both

That boundary keeps Linkar portable while still making local automation practical.

## What belongs in a site pack

A site-oriented pack can reasonably contain three different layers:

1. `templates/`
   Reusable workflow definitions.
2. `functions/`
   Binding-time helper functions used to resolve params for templates.
3. `discovery/`
   Read-only helpers that help an agent or service find likely projects, data directories, or references.

An example pack layout:

```text
izkf_pack/
  linkar_pack.yaml
  templates/
    demultiplex/
    cellranger_atac/
    dgea/
  functions/
    get_demultiplex_fastq_dir.py
    get_host_max_cpus.py
  discovery/
    projects.py
    fastq_runs.py
    raw_runs.py
    references.py
```

## Why discovery should not live in bindings

Bindings are best for workflow resolution, for example:

- turn the latest `demultiplex.demux_fastq_files` output into one `fastq_dir`
- derive a default reference
- compute sensible cores and memory

Bindings are not the best place for broader inventory questions like:

- list all projects on this server
- list all FASTQ runs under a facility root
- search all reference directories

Those are environment discovery tasks, not template-param resolution tasks.

## Why discovery in the pack works well

Putting discovery into the pack gives you a good compromise:

- Linkar core stays generic
- the pack can still encode local operational knowledge
- agents can discover likely context before asking Linkar to resolve or run anything

That means an agent can do:

1. use pack discovery to find candidate projects or FASTQ runs
2. let the user choose the right one
3. use Linkar API or MCP tools to inspect templates
4. resolve params
5. run the chosen workflow

## Good discovery outputs

Discovery helpers should usually return summaries, not huge internal blobs.

Good project summary:

```json
{
  "kind": "project_summary",
  "id": "260330_Yildiz_ZimmerBensch_BioII_scATAcseq",
  "path": "/data/projects/260330_Yildiz_ZimmerBensch_BioII_scATAcseq",
  "has_project_yaml": true,
  "linkar_runs": 2
}
```

Good FASTQ summary:

```json
{
  "kind": "fastq_run_summary",
  "name": "260330_A01742_0623_AHL7YGDRX7",
  "path": "/data/fastq/260330_A01742_0623_AHL7YGDRX7",
  "fastq_file_count": 48
}
```

This is enough for an agent to present options without dragging in full run metadata too early.

## The operational model

The practical split is:

- **Linkar** answers: what can I run, what does it need, what happened before, and what did it produce?
- **pack discovery** answers: what local data or projects are likely relevant?

That is often all an AI agent needs to reproduce what a human operator does with the CLI.
