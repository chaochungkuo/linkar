---
title: Packs, bindings, and projects
description: Packs distribute reusable templates and bindings. Projects record local runs and working context without absorbing the reusable assets.
order: 2
---

A pack is the reusable asset. A project is the local working context.

That separation matters because Linkar is trying to preserve both reuse and customization.

## What a pack is

A pack is where reusable capability lives.

It can contain:

- one or more templates
- pack-level bindings
- pack-level discovery helpers for site-specific context
- pack-level documentation
- custom helper functions used by bindings

Today the canonical pack contract file is `linkar_pack.yaml`.

Packs are meant to travel:

- between users
- between projects
- between machines
- eventually between Git repositories cleanly

This is why pack content should stay independent of one specific local project's run history.

## Why bindings belong in the pack

Bindings are part of the reusable definition of how work connects.

They encode things like:

- which output from one template should feed another template
- how default values should be resolved
- which custom transformation or path-selection function should be reused

If this logic is important enough to repeat, it belongs in a reusable asset rather than in manual
operator steps.

## What a project is

A project is where you do local work.

It records:

- which packs are attached
- which runs happened locally
- where stable run aliases point
- where immutable run history lives under `.linkar/runs/`

It should stay readable on disk. Linkar should not turn the project into a hidden database or a
workflow-definition language.

## Why this separation matters

If packs and projects collapse into one thing, several problems appear quickly:

- templates become harder to share
- bindings and custom logic become harder to reuse
- project-specific assumptions leak into reusable assets
- local run history becomes mixed with distributed template definitions
- reproducibility gets harder to explain

By keeping them separate, Linkar gets a cleaner model:

- packs distribute capability
- projects record local usage and state

## How this looks on disk

A pack might look like:

```text
example_site_pack/
  linkar_pack.yaml
  discovery/
    projects.py
    input_runs.py
    references.py
  functions/
    resolve_reference.py
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

## Where site-specific discovery belongs

Some environments need extra discovery logic that is not part of Linkar core:

- where projects are usually stored
- how FASTQ runs are named locally
- where references live on this server
- how to search local facility data before choosing a template input

That logic belongs naturally with the site pack, not in Linkar core and not in the project.

A good mental split is:

- `templates/` define reusable workflows
- `functions/` support binding-time param resolution
- `discovery/` holds read-only helpers for site-specific context lookup

This keeps Linkar generic while still letting a pack capture local operational knowledge.

## What bindings belong to

Pack-level bindings belong with the pack because they describe how templates in that pack relate to
one another and how reusable customization should happen.

Project-level pack selection belongs with the project because it describes the local working
context.

That split keeps reusable behavior in the reusable asset while keeping local choices visible.

## Design consequence

Once you accept this separation, a lot of Linkar's behavior becomes simpler:

- packs can be reused without project baggage
- bindings can encode repeated chaining logic once
- projects stay inspectable by humans and agents
- run artifacts stay on disk in normal directories
- the CLI can stay short because project discovery is local

That is the point of the model. It is not just file organization. It is the boundary that keeps the
tool understandable.
