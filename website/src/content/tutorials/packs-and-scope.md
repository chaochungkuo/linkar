---
title: Using global packs vs project packs
description: Understand lookup precedence and how to keep reproducibility strong.
order: 2
status: ready
---

Linkar resolves packs in this order:

1. Explicit `--pack`
2. Project-configured packs
3. Global packs from `linkar config pack ...`

That order is important because it keeps convenience available without weakening reproducibility.
A new project with no project-local packs can still use your global configured packs.

## Use `--pack` for one-off runs

This is the most explicit path:

```bash
linkar run simple_echo --pack ./examples/packs/basic --param name=Linkar
```

It is useful when:

- you are exploring a pack
- you do not want to modify project state
- you want the command itself to say exactly where the template came from

## Use project packs when the project needs its own pack setup

Add the pack to the project when that project should carry its own pack selection or binding:

```bash
linkar project init --name study
cd study
linkar pack add ../examples/packs/basic --id basic
linkar templates
linkar run simple_echo --name Linkar
```

Now the project remembers the pack, so later runs are shorter and the pack choice is saved with the
project.

Use this when:

- the project should stay portable without relying on your personal config
- the project needs a project-specific binding such as `--binding default`
- this project should use a different pack selection than your usual default

## Use global packs as the normal personal default

Global packs are personal defaults and are often enough on their own:

```bash
linkar config pack add ./examples/packs/basic --id basic
linkar templates
```

They are useful when you repeatedly use the same pack across many directories and do not need each
project to repeat that setup.

This is a good default for most day-to-day work.

Move a pack into project config only when the project needs to be explicit about it.

## What this means in practice

- `--pack` wins when you want full explicitness
- global packs are the normal personal default
- project packs override global ones for project-specific behavior and reproducibility

If a template id exists in multiple packs, use `--pack` or select the active project pack
explicitly. That keeps resolution deterministic and readable.

## Recommended habit

For most personal work:

1. configure your common pack once with `linkar config pack add`
2. initialize projects without repeating pack setup
3. add a project pack only when that project needs a different pack or binding

For a project that should carry its own pack definition:

1. initialize the project
2. add the pack to the project
3. run templates without repeating `--pack`
4. use `--pack` only for overrides or one-off comparisons

That keeps the command path short without making the source of a template ambiguous.
