---
title: Walk through the bundled example packs
description: Move from the smallest shell template to chaining, pack collisions, and remote-pack demos.
order: 4
status: ready
---

Linkar now ships example packs in tiers.

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

Finally, inspect the other example sets:

- `examples/packs/pack_management` for duplicate template ids and active-pack selection
- `examples/packs/remote` for Git-backed pack demonstrations
