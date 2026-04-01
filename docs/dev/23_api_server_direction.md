# API Server Direction

This document describes the intended direction for the Linkar API server.

The purpose is to keep the server thin over the core now that the execution model is mature enough to expose locally.

## Primary Rule
The external API must mirror core semantics.

It should not invent:

- a second execution model
- different parameter resolution rules
- different project semantics
- hidden server-only workflow behavior

The API server should be a transport layer over the core, just as the CLI is.

## Purpose
The first API server should provide:

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
The API should expose resources corresponding to existing core concepts:

- `projects`
- `templates`
- `runs`
- `packs`
- `bindings`

These should map directly to the filesystem-centered and metadata-centered design already defined in the core docs.

## MVP Operations
The first local API server should expose:

- `GET /health`
- `GET /templates`
- `GET /templates/<template_id>`
- `GET /projects/runs`
- `GET /projects/assets`
- `GET /runs/<run_ref>`
- `GET /runs/<run_ref>/outputs`
- `GET /runs/<run_ref>/runtime`
- `GET /methods`
- `POST /resolve`
- `POST /run`
- `POST /test`

These operations should remain thin wrappers over the same core semantics.

## Error Model
The API server should map typed core errors to stable machine-facing responses.

Because of this, the core should continue to prefer:

- structured errors
- stable error categories
- explicit return values

This is more important than building HTTP endpoints early.

## Response and Error Shape
The local API should:

- return JSON only
- map typed core errors to stable machine-facing error codes
- avoid server-only response semantics that are not grounded in the core

Recommended shapes:

```json
{"ok": true, "data": {...}}
```

```json
{"ok": false, "error": {"code": "template_not_found", "message": "..."}}
```

## Why This Doc Exists
The purpose of this direction doc is to prevent two common mistakes:

1. building an API server too early
2. shaping the core around imagined server behavior instead of stable runtime semantics

## Summary
The API server should be:

- thin over the core
- resource-oriented
- semantically aligned with the CLI and core API
- introduced only after the runtime model is already strong
