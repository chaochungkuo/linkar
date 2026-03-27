---
title: Authoring a template with script.sh
description: Develop a source script, let Linkar render run.sh, and keep runs rerunnable.
order: 3
status: draft
---

Template authors work on `script.sh` directly. Linkar resolves parameters, copies `script.sh` into the run directory, then generates `run.sh` as the runnable entrypoint with frozen values.

That gives you both:

- a developer-friendly source script
- a self-contained rendered run directory
