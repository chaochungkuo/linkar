# API Server Direction

This document describes the intended direction for a future Linkar API server.

The purpose is to define boundaries early enough that the core can be shaped correctly, without prematurely building a service layer before the execution model is mature.

## Primary Rule
The external API must mirror core semantics.

It should not invent:

- a second execution model
- different parameter resolution rules
- different project semantics
- hidden server-only workflow behavior

The API server should be a transport layer over the core, just as the CLI is.

## Purpose
A future API server may provide:

- programmatic project inspection
- template discovery
- run execution
- run inspection
- methods generation
- agent-oriented integrations

## Non-Goals for the First API Layer
The first API layer should not attempt to solve:

- multi-user collaboration
- authentication and authorization platform design
- distributed scheduling
- remote execution orchestration
- server-side domain logic outside the core

These can be considered later if the core remains stable.

## Canonical Resources
The future API should likely expose resources corresponding to existing core concepts:

- `projects`
- `templates`
- `runs`
- `packs`
- `bindings`

These should map directly to the filesystem-centered and metadata-centered design already defined in the core docs.

## Likely Operations
Representative operations include:

- inspect project state
- list available templates
- resolve project assets
- run a template
- inspect a run
- generate methods text

These operations already exist or are emerging in the core API and should remain the semantic source of truth.

## Error Model
The API server should map typed core errors to stable machine-facing responses.

Because of this, the core should continue to prefer:

- structured errors
- stable error categories
- explicit return values

This is more important than building HTTP endpoints early.

## Why This Doc Exists
The purpose of this direction doc is to prevent two common mistakes:

1. building an API server too early
2. shaping the core around imagined server behavior instead of stable runtime semantics

## Summary
The future API server should be:

- thin over the core
- resource-oriented
- semantically aligned with the CLI and core API
- introduced only after the runtime model is already strong
