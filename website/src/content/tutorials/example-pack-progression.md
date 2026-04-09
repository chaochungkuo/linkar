---
title: Walk through the bundled example packs
description: Move from the smallest shell template to chaining, pack collisions, and remote-pack demos.
order: 8
status: ready
---

Use this tutorial when you want to learn Linkar by reading and running the bundled packs in a
useful order.

Each step below answers a different question. Stop once you have learned the part you need.

## 1. Learn the template contract with `basic`

Start here if you need to understand what one standalone template looks like today.

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

What you should notice:

- `simple_echo` shows `run.command`
- `simple_file_input` and `fastq_stats` show `run.sh`
- `download_test_data` shows `run.py`
- `glob_reports` shows declared `glob` outputs
- `portable_python` shows `tools.required_any`
- `pixi_echo` and `pixi_pytest` show template-local environment files
- every template keeps its own local test entrypoint

If you only need template authoring basics, you can stop here.

## 2. Learn pack-level chaining with `chaining`

Move here once one standalone template is clear and you want to see how packs connect templates.

```bash
linkar project init --name chaining-demo
cd chaining-demo
linkar pack add ../examples/packs/chaining --id chaining --binding default
linkar run produce_message --message "hello"
linkar run consume_message
```

What you should notice:

- the pack is added with `--binding default`
- `consume_message` resolves its input from project history through the pack binding
- the user does not manually re-enter the produced message path

This is the smallest working example of Linkar's chaining model.

## 3. Compare defaults and caller overrides with `binding_overrides`

Use this when you want to see where customization belongs.

```bash
linkar project init --name binding-demo
cd binding-demo
linkar pack add ../examples/packs/binding_overrides --id binding_overrides --binding default
linkar run produce_data --value project
linkar run consume_data
linkar run consume_data --binding ../examples/packs/binding_overrides/override_binding
```

What you should notice:

- the default binding uses the latest project output from `produce_data`
- the explicit override binding ignores that and resolves a different source
- the same template can stay reusable while the caller still has an escape hatch

This is the best example for understanding why bindings are part of the pack model.

## 4. Learn pack selection with `pack_management`

Use this when you need to understand how Linkar behaves if multiple packs expose the same template
id.

What this example teaches:

- duplicate template ids across packs
- active-pack selection
- why `--pack` is the most explicit override

This is less about authoring and more about predictable resolution behavior.

## 5. Learn remote pack references with `remote`

Use this once local packs are already clear.

What this example teaches:

- `git+` or GitHub-style pack references
- local caching of remote assets
- revision-aware provenance for remote packs

## What each pack teaches

### `basic`

Use this pack first. It covers:

- the smallest template contract
- `run.command` vs `run.sh`
- `run.py`
- `linkar run ...` vs `linkar render ...`
- file inputs
- explicit defaults
- `glob` outputs
- `tools.required_any`
- `test.py` vs `test.sh`
- declared outputs with `path` and `glob`

### `chaining`

Use this when the single-template model is already clear. It shows:

- how one template consumes another template's outputs
- how pack-level default binding works
- how project state participates in resolution

### `binding_overrides`

Use this when you want to compare:

- pack defaults
- project choices
- explicit override binding at runtime

### `pack_management`

Use this to understand:

- duplicate template ids across packs
- active pack selection
- when `--pack` is the right explicit override

### `remote`

Use this once local packs are already clear. It demonstrates:

- Git-backed pack assets
- the same runtime model with a remote source

## Recommended order

1. `basic`
2. `chaining`
3. `binding_overrides`
4. `pack_management`
5. `remote`

That sequence matches the current product model:

1. one template
2. one pack with reusable chaining
3. one override mechanism
4. one resolution rule for multiple packs
5. one remote-pack source model
