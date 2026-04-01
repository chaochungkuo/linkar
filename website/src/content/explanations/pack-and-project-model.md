---
title: Pack and project model
description: Packs distribute reusable templates. Projects record local run history and chosen defaults.
order: 2
---

A pack is a distributable asset. A project is local working state.

That separation is one of the main reasons Linkar stays small.

## What a pack is

A pack is where reusable templates live.

It can contain:

- one or more templates
- pack-level default bindings
- pack-level documentation

Today the canonical pack contract file is `linkar_pack.yaml`.

Packs are meant to travel:

- between users
- between projects
- between machines
- eventually between Git repositories cleanly

That is why they should not depend on one specific project's run history.

## What a project is

A project is where you do local work.

It records:

- which packs are attached
- which runs happened locally
- where stable run aliases point
- where immutable run history lives under `.linkar/runs/`

It should stay readable on disk. Linkar should not turn it into a hidden database or a workflow
definition language.

## Why this separation matters

If packs and projects collapse into one thing, several problems appear quickly:

- templates become harder to share
- project-specific assumptions leak into reusable assets
- local run history becomes mixed with distributed template definitions
- reproducibility gets harder to explain

By keeping them separate, Linkar gets a cleaner model:

- packs distribute capability
- projects record local usage

## How this looks on disk

A pack might look like:

```text
izkf_genomics_pack/
  linkar_pack.yaml
  templates/
    fastqc/
    multiqc/
    demultiplex/
```

A project might look like:

```text
study/
  project.yaml
  fastqc -> .linkar/runs/fastqc_001
  multiqc -> .linkar/runs/multiqc_001
  .linkar/
    runs/
      fastqc_001/
      multiqc_001/
```

The pack tells Linkar what can be run. The project tells Linkar what was run locally.

## What bindings belong to

Pack-level default bindings belong with the pack because they describe how templates in that pack
relate to one another.

Project-level pack selection belongs with the project because it describes the local working
context.

That split keeps default behavior reusable without hiding local choices.

## Design consequence

Once you accept this separation, a lot of Linkar's behavior becomes simpler:

- packs can be reused without project baggage
- projects stay inspectable by humans and agents
- run artifacts stay on disk in normal directories
- the CLI can stay short because project discovery is local

That is the point of the model. It is not just file organization. It is the boundary that keeps the
tool understandable.
