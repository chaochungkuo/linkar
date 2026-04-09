---
title: Test the bundled basic templates
description: Use linkar test for the normal validation path, then fall back to test.sh or test.py when editing one template locally.
order: 6
status: ready
---

Start with `linkar test`.

From the repository root:

```bash
linkar test simple_echo --pack ./examples/packs/basic
linkar test simple_file_input --pack ./examples/packs/basic
linkar test simple_boolean_flag --pack ./examples/packs/basic
linkar test download_test_data --pack ./examples/packs/basic
linkar test fastq_stats --pack ./examples/packs/basic
linkar test glob_reports --pack ./examples/packs/basic
linkar test portable_python --pack ./examples/packs/basic
linkar test pixi_echo --pack ./examples/packs/basic
linkar test pixi_pytest --pack ./examples/packs/basic
```

This is the normal path because it validates the template through Linkar itself:

- Linkar resolves the template from the pack
- Linkar chooses `test.sh` or `test.py`
- Linkar creates a temporary test workspace
- Linkar records runtime details under `.linkar/tests/...`

## Use direct local testing while editing

When you are actively editing one template, the faster loop is to run its local test entrypoint directly from the template folder.

Shell-based template tests:

```bash
cd examples/packs/basic/templates/simple_boolean_flag
bash test.sh
```

Python-based template tests:

```bash
cd examples/packs/basic/templates/pixi_pytest
python test.py
```

That local path is useful while authoring, but `linkar test` is still the better final check
because it exercises the actual Linkar contract.

## Which test entrypoint should a template use?

Use `test.sh` when the template is naturally shell-oriented.

Use `test.py` when the template test is more natural in Python, for example when:

- assertions are easier to write in Python
- the template already uses Python tooling
- you want to inspect files or XML/JSON output directly

Linkar supports either `test.sh` or `test.py`, but a template should only define one of them.

## When to use `linkar run`

`linkar test` checks that the template is healthy.

`linkar run` performs a real run and creates the recorded run artifact.

For example:

```bash
linkar run fastq_stats \
  --pack ./examples/packs/basic \
  --param input_fastq=./examples/packs/basic/templates/fastq_stats/testdata/sample.fastq \
  --param sample_name=demo
```

That creates a real run directory under `.linkar/runs/` or under the current project if a project is active.
In project mode, the project root exposes a stable path such as `./fastq_stats`, while the immutable recorded artifact lives under `.linkar/runs/<instance_id>/`.
