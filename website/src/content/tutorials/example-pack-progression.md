---
title: Walk through the bundled example packs
description: Move from the smallest shell template to chaining, pack collisions, and remote-pack demos.
order: 4
status: ready
---

Linkar ships example packs in tiers.

The goal is to teach one new idea at a time, not to provide a random sample directory.

Start with the basic pack:

```bash
linkar test simple_echo --pack ./examples/packs/basic
linkar test simple_file_input --pack ./examples/packs/basic
linkar test simple_boolean_flag --pack ./examples/packs/basic
linkar test download_test_data --pack ./examples/packs/basic
linkar test fastq_stats --pack ./examples/packs/basic
linkar test pixi_echo --pack ./examples/packs/basic
linkar test pixi_pytest --pack ./examples/packs/basic
```

Then move to project-aware examples:

```bash
linkar project init --name chaining-demo
cd chaining-demo
linkar pack add ../examples/packs/chaining --id chaining --binding default
linkar run produce_message --message "hello"
linkar run consume_message
```

Then inspect binding selection explicitly:

```bash
linkar project init --name binding-demo
cd binding-demo
linkar pack add ../examples/packs/binding_overrides --id binding_overrides --binding default
linkar run produce_data --value project
linkar run consume_data
linkar run consume_data --binding ../examples/packs/binding_overrides/override_binding
```

Finally, inspect the other example sets:

- `examples/packs/pack_management` for duplicate template ids and active-pack selection
- `examples/packs/remote` for Git-backed pack demonstrations

## What each pack teaches

### `basic`

Use this pack first. It covers:

- the smallest template contract
- `run.command` vs `run.sh`
- `linkar run ...` vs `linkar render ...`
- file inputs
- explicit defaults
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

That sequence matches how the product is meant to be learned.
