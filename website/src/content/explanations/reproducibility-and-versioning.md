---
title: Reproducibility and versioning
description: What Linkar records, what it leaves to the wrapped tool, and how packs should think about pinned versus floating upstreams.
order: 7
---

Linkar improves reproducibility, but it does not create it automatically from nothing.

## What Linkar records reliably

For every recorded run, Linkar can capture:

- resolved params
- param provenance
- declared outputs
- collected outputs
- pack ref and revision when available
- binding ref
- command
- timestamps
- warnings

This is enough to explain what Linkar asked the template to do.

## What Linkar does not control

Linkar does not automatically pin:

- external binaries on the host
- remote APIs
- floating Git repos cloned by a template
- hidden behavior inside wrapped tools

That is why template authors still need to make packaging decisions deliberately.

## Vendored snapshot versus runtime clone

For an external upstream repository, there are two reasonable packaging models.

### Vendored snapshot

Bundle the upstream code into the template pack.

Use this when:

- the template should be self-contained
- render artifacts should include the real implementation
- you want the exact code snapshot to travel with the pack

### Runtime clone

Clone the upstream repo during `run` or when executing a rendered artifact.

Use this when:

- you want a thinner pack
- upstream already has its own release cycle
- you are comfortable with a network dependency at execution time

If you use runtime clone, pin the commit when you care about reproducibility. Floating `main` is
convenient, but it is not a stable scientific contract.

## Render artifacts are meant to be readable

Rendered `run.sh` files should be easy to inspect and edit.

Conventions that support this:

- one final `run.sh`
- resolved values in the script
- localized bound files copied into the rendered directory
- visible placeholders such as `__EDIT_ME_GENOME__`
- no unnecessary Linkar wrappers

That makes render artifacts useful both for handoff and for controlled manual edits.
