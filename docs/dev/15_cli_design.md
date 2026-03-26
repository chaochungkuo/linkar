# CLI Design

This document defines the role and shape of the Linkar CLI.

The CLI should make the common path short while staying thin. It is an interface to the core, not a second execution engine.

## Design Goals
The CLI should be:

- simple for demo use
- short for common interactive work
- explicit when needed for scripting
- thin over the core API

## Core Rule
The CLI parses arguments, discovers context, and calls the core.

It should not:

- duplicate resolution logic
- implement separate project semantics
- invent behavior that the core API does not share

## Common Behavior
For normal interactive use:

- the current directory is the default project context candidate
- `project.yaml` should be auto-discovered there
- explicit `--project` style arguments are optional, not required for the common path

This keeps demo commands short:

```bash
cd study
linkar run bclconvert --param bcl_dir=/data/run42
linkar run fastqc
linkar run rnaseq
```

## Initial Commands
The initial CLI surface should stay small:

- `linkar project init`
- `linkar run`

Pack and binding selection may start with explicit path or URL references and later move into project-level configuration once reuse matters more than one-off invocation.

## `linkar project init`
Purpose:

- create a minimal `project.yaml`
- mark a directory as a Linkar project

Example:

```bash
linkar project init .
```

## `linkar run`
Purpose:

- identify the template
- discover the active project if present
- accept explicit parameter overrides
- optionally accept pack or binding references for ad hoc use
- delegate execution to the core

Example:

```bash
linkar run bclconvert --param bcl_dir=/data/run42
```

## Parameters
The CLI should accept repeated parameter inputs in a simple form such as:

```bash
--param key=value
```

This keeps the CLI generic across templates without generating per-template subcommands.

## Packs and Bindings
Packs and bindings should be loadable in a similar way for simplicity.

Likely forms:

- local path
- Git or GitHub URL
- future registry reference

Examples of ad hoc use:

```bash
linkar run rnaseq --pack github:org/genomics-pack
linkar run rnaseq --pack git+https://github.com/org/genomics-pack.git
linkar run rnaseq --pack github:org/genomics-pack --binding github:facility/core-binding
```

For repeated use, the preferred model is project-level per-pack configuration so the normal command can stay short:

```bash
cd study
linkar run rnaseq
```

The important implementation rule is:

- ad hoc `--binding` applies to the selected pack for that invocation
- project configuration should record binding choice alongside the relevant pack entry

## Error Handling
The CLI should:

- display clear validation and execution errors
- avoid hiding the underlying issue
- rely on the core for semantics

The core should decide what is valid.
The CLI should decide how to present that result to a human.

## Future Commands
Future versions may add commands for:

- project inspection
- metadata inspection
- methods generation
- pack discovery

These should only be added when the core behavior is already well-defined.

## Summary
The Linkar CLI should stay:

- short in the common case
- thin over the core
- explicit when necessary
- consistent with the filesystem-centered project model
