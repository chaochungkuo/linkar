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

## Use `--pack` for one-off runs

This is the most explicit path:

```bash
linkar run fastqc --pack ~/github/izkf_genomics_pack --input sample.fastq.gz
```

It is useful when:

- you are exploring a pack
- you do not want to modify project state
- you want the command itself to say exactly where the template came from

## Use project packs for real study work

Once a project should be reproducible on its own, add the pack to the project:

```bash
linkar project init --name study
cd study
linkar pack add ~/github/izkf_genomics_pack --id izkf
linkar templates
linkar run fastqc --input sample.fastq.gz
```

Now the project remembers the pack, so later runs are shorter and the project remains readable.

This is the recommended path for normal work.

## Use global packs for personal convenience

Global packs are personal defaults:

```bash
linkar config pack add ~/github/izkf_genomics_pack --id izkf
linkar templates
```

They are useful when you repeatedly use the same pack across many directories.

But global configuration should not be your only reproducibility story. A project should still be
able to stand on its own.

## What this means in practice

- `--pack` wins when you want full explicitness
- project packs are the best default for real work
- global packs are convenience, not project definition

If a template id exists in multiple packs, use `--pack` or select the active project pack
explicitly. That keeps resolution deterministic and readable.

## Recommended habit

For a real project:

1. initialize the project
2. add the pack to the project
3. run templates without repeating `--pack`
4. use `--pack` only for overrides or one-off comparisons

That keeps the command path short without making the source of a template ambiguous.
