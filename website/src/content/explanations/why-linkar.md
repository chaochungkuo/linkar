---
title: Why Linkar stays small
description: Scripts are flexible but opaque. Workflow engines are powerful but heavy. Linkar stays in the middle on purpose, with interfaces for both humans and agents.
order: 1
---

Linkar should not drift into a general DAG platform.

It works best as a small runtime for reusable computational templates:

- strong provenance
- readable project state
- a short CLI for humans
- a structured core and local API for agents

That constraint is a product decision, not a missing feature.

## The gap it tries to fill

Many computational workflows start in one of two places:

### Ad hoc scripts

These are flexible and fast to write, but they usually become hard to reuse:

- parameters are implicit
- outputs are informal
- provenance is weak
- downstream chaining is brittle

### Full workflow systems

These are powerful, but they often ask for a lot up front:

- a workflow language
- a scheduler model
- a graph model
- a bigger cognitive load than one reusable step actually needs

Linkar sits in the middle.

It helps you package one computational step cleanly without forcing you into a full workflow
platform.

## What Linkar is good at

Linkar is strong when you want to:

- turn one analysis step into a reusable template
- keep run artifacts inspectable on disk
- expose parameters and outputs explicitly
- chain a few steps through recorded outputs
- support both human CLI use and agent-oriented automation

## What Linkar should not become

Linkar should not quietly expand into:

- a DAG authoring language
- a scheduler
- a cluster orchestrator
- a registry-first platform
- a hidden state database

Those tools exist already. Linkar is more valuable when it keeps its scope narrow and readable.

## Why the human and agent interfaces both matter

The product is not only about provenance. The interface model is part of the value.

For humans:

- the common CLI path should stay short
- the current project should be discovered automatically
- the run artifact should be understandable from the filesystem

For agents:

- parameters should be structured
- outputs should be structured
- metadata should be easy to inspect
- the same semantics should exist in the core API and local server

That dual-interface design is one of Linkar's strongest differentiators.

## The real product thesis

Linkar is a small runtime for reusable computational templates, with a short human CLI and a
machine-readable execution model.

It does not try to hide the filesystem.
It does not try to own the whole workflow.
It tries to make one step reusable, inspectable, and easy to connect to the next one.
