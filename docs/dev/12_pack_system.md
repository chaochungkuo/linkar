# Pack System

This document defines the role of packs in Linkar.

A pack is the unit of distribution for reusable Linkar assets. Packs let users share templates and functions without putting domain-specific logic into the core.

Packs are purposeful bundles. They may collect templates that belong together for a scientific or operational use case, and they may optionally ship a default binding profile that makes the bundle practical out of the box.

## Purpose
Packs exist to provide:

- reusable template collections
- reusable function collections
- an optional default binding for that collection
- versionable distribution units
- a boundary between generic core behavior and domain-specific logic

## Basic Structure
A pack should typically look like:

```text
pack/
  templates/
  functions/
  binding.yaml   # optional default binding
```

Example:

```text
bio-pack/
  templates/
    bclconvert/
    fastqc/
    rnaseq/
  functions/
    get_latest_fastq.py
  binding.yaml
```

## Contents
### `templates/`
Contains template directories.

Each template should conform to the template specification.

### `functions/`
Contains reusable functions used for:

- parameter resolution
- binding logic
- lightweight lifecycle assistance

### `binding.yaml`
Optional.

This may define the pack's default binding profile.

The important rule is:

- a pack may provide a default binding
- a project may choose to use that default binding for that pack
- a project may also override it with another binding for that pack

This keeps packs useful out of the box without making them rigid.

## Distribution Model
The initial pack model should be Git-based.

That is enough for early versions because it provides:

- version control
- reviewable changes
- simple sharing
- stable references

Future registry features may sit on top of this, but Git should remain a viable base distribution model.

Longer term, packs may also be distributed through a template or asset registry in a Docker-Hub-like way. That future should not change the core rule that templates remain standalone and testable.

## Loading Model
Packs should be loadable in a simple, symmetric way:

- local path
- Git or GitHub URL
- future registry reference

This should work both for one-off use and for project-level reuse.

Examples:

- `/opt/linkar/packs/genomics-pack`
- `github:org/genomics-pack`
- `git+https://github.com/org/genomics-pack.git`

Remote references should resolve through Linkar's asset cache rather than being unpacked directly into the project directory.

## Pack Responsibilities
A pack is responsible for:

- organizing reusable assets
- carrying domain-specific logic
- optionally providing a default binding profile
- providing stable template ids within its scope

A pack is not responsible for:

- project execution state
- scheduling
- global package/environment management
- forcing one fixed binding choice in all environments

## Relationship to Templates
Templates are the atomic reusable units.

This means:

- a template should remain runnable with explicit params even outside a pack
- a pack should improve convenience and coherence, not destroy portability
- pack-level defaults should be additive, not mandatory

This distinction is important for the long-term sharing model where users may want to pull and run individual templates independently.

## Design Rules
To keep packs coherent:

- templates should remain individually understandable
- functions should remain narrow and reusable
- pack structure should be inspectable from the filesystem
- packs should not require a service layer to be useful
- default bindings should remain replaceable

## Future Extensions
Future versions may add:

- pack metadata
- pack version identifiers in run metadata
- template registries
- remote pack discovery

These should extend the pack model rather than replace the simple filesystem-plus-Git foundation.

## Summary
Packs are how Linkar scales reuse without bloating the core:

- they hold templates and functions
- they may ship a default binding
- they carry domain-specific behavior
- they are portable and versionable
- they keep the core generic
