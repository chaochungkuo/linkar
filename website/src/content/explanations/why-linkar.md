---
title: Why Linkar exists
description: "Linkar is for the tension between customization and reuse: turning useful analysis resources into reusable building blocks without making them rigid."
order: 1
---

Linkar starts from a very common data-science problem.

Useful work already exists in many forms:

- a CLI tool you wrap for one dataset
- a Python package you call from a small script
- a notebook that contains the core logic for a recurring task
- a shell script someone on the team already trusts

You want to customize these resources for the current analysis. You also want to reuse them next
time without rebuilding the same glue again.

That is the tension Linkar is designed for: keep useful work flexible enough for real projects,
but structured enough to reuse and connect safely.

## The problem Linkar tries to solve

Without a shared structure, customization and reuse fight each other:

- parameters stay implicit
- outputs stay informal
- custom path rewiring gets repeated by hand
- downstream chaining becomes brittle
- the same transformation logic gets copied from one run to the next

That is especially painful when one analysis step feeds another. People end up manually changing
params, paths, and defaults again and again. It is slow and easy to get wrong.

## What Linkar provides

Linkar is the core runtime.

It gives you:

- a human CLI for daily use
- a local API and MCP interface for machines
- explicit input and output contracts
- readable run artifacts on disk
- a reusable place to define chaining and customization logic

The key unit is not a whole workflow. It is the reusable analysis resource.

## The core idea

A Linkar pack captures two things:

### Templates

Templates are standalone functional units.

They define:

- input params
- output params
- the files, scripts, helpers, and environment config needed to run
- local test scripts so the template can be tested on its own

Each template should remain understandable and testable without depending on another template.

### Bindings

Bindings define how templates connect.

They let you encode:

- how outputs from template A become inputs to template B
- custom resolution logic
- repeated transformations or conventions the user should not redo manually

Once this logic is written once, it becomes reusable instead of living in ad hoc notes or shell
history.

## Why this matters

This model gives Linkar a very specific role:

- reusable enough to share
- flexible enough to customize locally
- explicit enough to chain safely
- structured enough for both humans and machines

Linkar is not trying to replace every workflow system. It is trying to make reusable analysis work
practical before you need a workflow platform.

## Why it stays intentionally scoped

Linkar works best when it stays focused on:

- reusable templates
- reusable bindings
- readable local projects
- a short CLI for people
- a structured API for machines

It should not drift into a general DAG language, scheduler, or hidden database.

That narrow scope is part of the product identity. Linkar is the layer that links reusable
resources together while keeping them understandable.
