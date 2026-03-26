# Vision and Philosophy

## Vision
Linkar is a lightweight execution engine for reusable computational templates.

Its purpose is to make analysis steps easy to run, easy to chain, and easy to understand later by both humans and AI systems. A Linkar run should produce not just files, but a self-describing artifact: what was run, with which parameters, in which context, and what it produced.

The long-term goal is to give researchers, engineers, and AI agents a simple substrate for computational work that sits between ad hoc scripts and heavy workflow systems.

## Problem Statement
Many real analysis pipelines begin as folders of scripts, shell commands, and handwritten notes. That style is fast at first, but weak in the places that matter later:

- Inputs and outputs are implicit.
- Parameters are scattered across commands or notebooks.
- Reuse is difficult because each script assumes local context.
- Chaining steps requires manual bookkeeping.
- Provenance is incomplete, which hurts reproducibility.
- AI systems can help generate commands, but they struggle to reason over unstructured execution history.

Linkar exists to solve this with a smaller abstraction surface than a full workflow engine.

## Product Thesis
The core idea is that a reusable computational step should be packaged as a template with:

- A clear parameter interface
- A standalone executable entrypoint
- A predictable output directory
- Machine-readable metadata

Projects then provide the minimum amount of state needed to connect runs together over time. Packs provide a way to distribute templates, shared functions, and optional default bindings. Functions provide lightweight resolution and transformation logic without turning the system into a general orchestration framework, while bindings remain replaceable overlays rather than fixed template requirements.

## What Linkar Is
Linkar is:

- A template runner
- A project-level state tracker
- A metadata producer for reproducibility and downstream reasoning
- A thin orchestration layer for chaining outputs across steps
- A foundation for future AI-assisted execution, inspection, and methods generation

## What Linkar Is Not
Linkar is not:

- An environment manager
- A container platform
- A strict DAG scheduler
- A replacement for Snakemake, Nextflow, Airflow, or similar systems
- A generic workflow language
- A data catalog or warehouse

When users need distributed scheduling, complex branching logic, or full workflow semantics, another system should sit above or around Linkar rather than Linkar trying to absorb that complexity.

## Primary Users
The design currently fits three overlapping users:

- Template authors who want to package one analysis step cleanly
- Project operators who want repeatable runs with traceable outputs
- AI agents that need a small, explicit API and structured execution records

The first version should bias toward correctness, explicitness, and inspectability over convenience shortcuts.

## Core Principles
### 1. Simplicity First
The system should preserve a very small set of concepts: Template, Project, Pack, and Function.

If a feature introduces a new concept, it should clear a high bar. Most new capabilities should instead refine one of the existing concepts.

### 2. Templates Own Execution Logic
A template should remain executable on its own. Linkar should orchestrate execution, not hide the actual work in framework internals.

That means:

- The run entry should be a normal script or program
- Parameters should be passed through a simple transport layer
- A template should remain understandable without reading Linkar internals

### 3. Core Owns Orchestration, Not Domain Logic
The core should handle parameter resolution, directory preparation, metadata writing, and project tracking. It should not embed domain-specific rules for genomics, imaging, ML, or any other field.

Domain knowledge belongs in packs and functions.

### 4. Reproducibility Is a Default Output
A run is incomplete unless it leaves behind enough structured information to explain itself later.

At minimum, Linkar should capture:

- Template identity
- Instance identity
- Resolved parameters
- Output locations
- Execution command
- Timestamp
- Relevant software version data when available

This should not be treated as optional polish.

### 5. Outputs Should Be Portable
A run directory should be a self-contained artifact as far as practical. Someone inspecting the directory later should be able to understand what happened without reconstructing state from a database or external service.

This is why metadata lives with the run rather than only in project state.

### 6. Chaining Should Be Lightweight
Many users need simple linear or loosely connected multi-step analyses, not a full graph language.

Linkar should make it easy to say, in effect, "use the latest relevant output from this project" without forcing users to define a formal DAG for every case.

### 7. AI-Readable by Design
AI-native does not mean letting the model guess. It means the system should expose explicit structure that an agent can inspect and act on safely.

That includes:

- Stable file locations
- Clear parameter schemas
- Structured metadata
- A small programmatic core API
- Minimal hidden behavior

### 8. Thin Interfaces Win
The CLI should stay thin. The future API server or UI should also stay thin. The important behavior belongs in the core so it can be reused consistently by humans, scripts, and agents.

### 9. The Common Case Should Be Short
For normal interactive use, Linkar should assume the current working directory is the project context and look for `project.yaml` there before asking for explicit project arguments.

Explicit flags should still exist for scripting and unusual layouts, but the demo experience should stay as close as possible to:

- `cd study`
- `linkar run bclconvert`
- `linkar run rnaseq`

## Design Implications
These principles imply several concrete design choices:

- `project.yaml` is a small state index, not a full database.
- `meta.json` is a first-class artifact, not debug output.
- Parameter transport should stay simple and universal.
- The CLI should auto-discover the current project by default.
- Templates should remain valid without binding; packs may add optional default binding for convenience.
- Project binding should prefer explicit conventions over magical inference.
- Ephemeral execution should exist for quick runs, but full chaining requires a project.
- The core API should be clean enough that a future UI or agent can call it directly.

## Non-Goals for the Early Versions
To keep the product sharp, the early versions should explicitly avoid:

- Complex conditional execution
- Implicit cross-project linking
- Built-in remote execution
- Rich templating languages inside the core
- Hidden mutation of templates at runtime
- Large plugin surfaces before the core concepts stabilize

If one of these becomes necessary, it should first be proven in packs or higher-level tooling.

## Success Criteria
Linkar is succeeding if the following are true:

- A template author can define and share a reusable step with minimal ceremony.
- A project operator can rerun and inspect work without guessing how a result was produced.
- A multi-step analysis can be chained through project outputs with little manual bookkeeping.
- An AI agent can inspect project state and metadata and make reliable next-step decisions.
- The system remains understandable from the filesystem layout and a few core APIs.

## Strategic Positioning
Linkar should occupy the space between raw scripts and heavyweight workflow platforms.

Compared with raw scripts, it adds structure, provenance, and reuse.
Compared with workflow engines, it keeps the abstraction surface small and execution model local and inspectable.

That middle position is only valuable if Linkar stays disciplined. If it grows into a complex workflow language, it loses the main reason to exist.

## Example
The intended user experience should feel as simple as:

```bash
mkdir study && cd study
linkar project init .
linkar run bclconvert --param bcl_dir=/data/run42
linkar run fastqc
linkar run rnaseq
```

Each run should leave behind a readable artifact, while the project tracks enough state to support chaining and later interpretation.
