---
title: Authoring a template with run.sh
description: Keep templates small with a real run.sh and either test.sh or test.py for local validation.
order: 3
status: draft
---

Template authors work on a real `run.sh` directly. Linkar resolves parameters and executes that runtime entrypoint during normal runs.

That gives you both:

- a developer-friendly runtime script
- a small test contract through `test.sh` or `test.py`

In direct mode, Linkar stages the runtime bundle into the run directory before execution. That lets templates depend on support files such as `pixi.toml`, helper scripts, or local config files without forcing authors to reach back into the source template directory at runtime.
