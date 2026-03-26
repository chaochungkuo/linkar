# System Architecture

This document describes how the Linkar system is organized at a high level. The goal is not to define many layers, but to keep a small architecture with clear responsibilities and stable boundaries.

## Architectural Goal
Linkar should have a compact architecture that supports three interfaces over time:

- CLI use by humans
- Programmatic use through the core API
- Future use through an API server or UI

All of these should rely on the same core execution logic. The architecture should make it difficult for behavior to drift between interfaces.

## Top-Level Layers
Linkar should be organized into the following layers:

### 1. Core
The Core contains the actual system behavior.

It is responsible for:

- Loading templates and projects
- Resolving parameters
- Discovering or creating execution context
- Preparing output directories
- Executing template entrypoints
- Writing metadata and runtime records
- Updating project state
- Exposing a reusable programmatic API

The core should be the source of truth for Linkar semantics.

### 2. CLI
The CLI is a thin interface for human use.

It is responsible for:

- Parsing arguments
- Discovering the current project context
- Calling the core API
- Displaying human-readable results and errors

The CLI should not reimplement run logic. It should be a transport layer into the core.

### 3. Future Service Layer
In later versions, Linkar may add:

- An API server
- A web UI
- Agent-facing orchestration tools

These should sit above the core in the same way as the CLI: they may shape requests and responses, but they should not redefine execution semantics.

## Primary Design Rule
The core must not depend on the CLI, UI, or API server.

This rule matters because the core should remain usable from:

- Local scripts
- Tests
- AI agents
- Future service interfaces

The dependency direction should always point inward toward the core.

## Logical Subsystems Inside the Core
The core is conceptually small, but it still contains several distinct responsibilities.

### Template Subsystem
Responsible for:

- Loading template definitions
- Searching configured pack roots when needed
- Validating template structure
- Locating entrypoints and parameter schemas

This subsystem handles template definitions, not project history.

### Project Subsystem
Responsible for:

- Loading `project.yaml`
- Discovering the active project from the current directory
- Exposing configured pack references and per-pack binding choices
- Recording template instances
- Indexing outputs and metadata references

This subsystem manages project state as a lightweight index.

### Resolution Subsystem
Responsible for:

- Applying parameter precedence
- Pulling values from CLI input
- Applying a selected binding for the active pack when present
- Pulling values from project outputs
- Applying defaults
- Invoking functions when bindings require them

This subsystem decides what values a run will actually use.

### Execution Subsystem
Responsible for:

- Determining the output directory
- Preparing the run directory
- Setting the execution environment
- Running the template entrypoint
- Capturing runtime details

This subsystem performs the actual run once inputs are resolved.

### Metadata Subsystem
Responsible for:

- Writing structured run metadata
- Capturing runtime details such as command and timestamps
- Ensuring outputs are recorded in a machine-readable way

This subsystem turns a run into a reproducible artifact.

## Filesystem as System Boundary
Linkar should treat the filesystem as a primary system interface, not just an implementation detail.

Important architectural consequences:

- Templates are defined as files and directories.
- Projects are represented by `project.yaml`.
- Each template instance has its own output directory.
- Metadata lives inside the run directory.
- Outputs are consumed through stable filesystem paths.

This is intentional. It keeps Linkar inspectable, portable, and compatible with both humans and automation.

## Execution Flow
The architecture should support the following high-level flow:

1. The user or caller invokes `linkar run` or the equivalent core API.
2. The interface layer identifies the template and current project context.
3. The core loads the template definition.
4. The core loads the project if one is present or explicitly requested.
5. The resolution subsystem computes the final parameter set.
6. The execution subsystem determines the output directory and prepares it.
7. The template entrypoint is executed.
8. The metadata subsystem writes run metadata and runtime records.
9. The project subsystem records the new template instance if a project is active.
10. The resulting outputs become available for later runs.

In compact form:

`CLI/API -> Core -> load template/project -> resolve params -> prepare run -> execute -> write metadata -> update project`

## Data Flow Model
Linkar data should flow through a simple chain:

- Template definition declares expected params
- Caller provides explicit params
- Project state provides prior outputs
- Functions refine or compute values where needed
- Resolved params are passed to the template entrypoint
- The run produces outputs
- Metadata records what happened
- Project state indexes the new instance for future reuse

This is intentionally not a scheduler graph. It is an execution-and-recording loop.

## Project Context Discovery
For normal CLI usage, the architecture should assume the current directory is the first project context candidate.

That means:

- The CLI should look for `project.yaml` in the current working directory by default.
- If found, that project becomes the active context.
- If not found, the run may proceed in ephemeral mode when valid.
- Explicit project arguments should remain available, but they are not the common path.

This keeps the CLI simple without changing the underlying core model.

## Execution Modes
The architecture currently supports or anticipates two execution modes:

- `direct`: execute the template entrypoint directly
- `render`: optionally render an execution artifact before running

The architecture should treat execution mode as template behavior, not as a separate product layer.

The common path should remain `direct`.

## Error Boundaries
Errors should be handled at the right layer:

- The core should raise structured, meaningful execution and validation errors.
- The CLI should format those errors for humans.
- Future API layers should translate those errors into stable machine-facing responses.

The core should not print user-facing CLI output as part of its normal behavior.

## Architectural Constraints
To keep the design coherent, the following constraints should hold:

- The core should not contain domain-specific science or business logic.
- The CLI should not duplicate parameter resolution or project indexing logic.
- Metadata should be generated by the core, not by templates ad hoc.
- A template should remain runnable without requiring a running service.
- Project state should remain file-based and transparent.
- New features should prefer extending existing subsystems rather than creating new top-level layers.

## Future Extension Points
The architecture leaves room for growth in a controlled way.

Likely extensions include:

- Richer metadata capture
- Function loading and binding execution
- Methods generation from project metadata
- A registry for packs and templates
- An API server and UI on top of the same core

These should extend the existing architecture, not replace it.

## Summary
The Linkar architecture is intentionally narrow:

- The core owns semantics.
- Interfaces stay thin.
- The filesystem is a first-class system boundary.
- Project state records history rather than defining workflows.
- Each run becomes a portable, self-describing artifact.

If this architecture remains disciplined, Linkar can stay simple while still supporting both human workflows and AI-native tooling.
