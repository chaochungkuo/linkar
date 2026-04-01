---
title: Authoring a template with run.sh
description: Keep templates small with a real run.sh and either test.sh or test.py for local validation.
order: 3
status: draft
---

Template authors work on a real `run.sh` directly. Linkar resolves parameters and executes that
entrypoint during normal runs.

That gives you:

- a normal runtime script
- a small test contract through `test.sh` or `test.py`

In direct mode, Linkar stages the runtime bundle into the run directory before execution. That lets
templates depend on support files such as `pixi.toml`, helper scripts, or local config files
without reaching back into the source template directory at runtime.

Declared outputs are resolved from that run artifact. By default, Linkar maps output names under
`results/`: `results_dir` becomes `results/`, `fastqc_dir` becomes `results/fastqc`, and other
names can be overridden with an explicit relative `path` in `linkar_template.yaml`.

When a template needs to expose many files, it can declare `glob`. Linkar evaluates that glob under
`results/` and records the matched paths as a list.

Downstream templates can consume those collections with the `list[path]` parameter type. Linkar
transports that list into the runtime environment as an `os.pathsep`-joined string so shell and
Python entrypoints can both read it predictably.
