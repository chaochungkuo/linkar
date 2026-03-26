# Function System

This document defines the role of functions in Linkar.

Functions provide reusable logic for cases where static configuration is not enough. They are intentionally narrower than a full plugin system and should stay that way.

## Purpose
Functions exist to support:

- parameter resolution
- binding logic
- lightweight transformation
- carefully scoped lifecycle assistance

They should extend the system without forcing domain-specific rules into the core.

## Why Functions Exist
Not all useful behavior can be expressed as:

- explicit CLI parameters
- project output lookup
- simple defaults

Functions provide a controlled escape hatch for these cases.

## Typical Use Cases
Examples:

- `get_latest_fastq(ctx) -> path`
- `resolve_reference_genome(ctx) -> path`
- `derive_sample_sheet(ctx) -> path`

These functions may be shipped:

- inside a pack as shared pack logic
- inside a separately distributed binding overlay

The core should not care which distribution route was used as long as the function contract is the same.

## Non-Goals
Functions should not become:

- a general plugin marketplace too early
- a hidden workflow engine
- a place for arbitrary side-effect-heavy execution

If functions become too powerful, they will make runs harder to understand and reproduce.

## Execution Context
Functions should receive a context object with the information needed to act safely.

That context may include:

- current template definition
- active project state
- resolved parameters so far
- pack-local resources
- runtime mode information

The context should be explicit rather than relying on global state.

## Design Constraints
Functions should be:

- deterministic where practical
- inspectable
- narrowly scoped
- reusable across templates

They should avoid:

- writing large amounts of hidden state
- modifying project history directly
- making network calls as implicit behavior unless clearly intended

## Lifecycle Hooks
Lifecycle-style functions may exist in future versions for:

- pre-run preparation
- post-run summarization

These should remain carefully constrained and should not blur the line between template logic and core orchestration.

## Summary
Functions are the lightweight logic layer of Linkar:

- smaller than plugins
- more dynamic than static config
- useful for resolution and transformation
- best kept narrow and explicit
