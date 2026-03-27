---
title: Using global packs vs project packs
description: Understand lookup precedence and how to keep reproducibility strong.
order: 2
status: draft
---

Linkar resolves packs in this order:

1. Explicit `--pack`
2. Project-configured packs
3. Global packs from `linkar config pack ...`

That keeps convenience available without weakening project reproducibility.
