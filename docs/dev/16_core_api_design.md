# Core API Design

This document defines the intended shape of the Linkar core API.

The core API is the semantic center of the system. The CLI, future UI, and future agent tooling should all rely on this layer rather than reimplementing behavior.

## Goals
The core API should provide:

- programmatic control over Linkar execution
- stable semantics across interfaces
- functions small enough for AI agents and UIs to call directly
- clean separation from presentation concerns

## Design Rules
The core API should:

- own execution semantics
- avoid CLI-specific assumptions
- operate on explicit inputs and return structured results
- raise meaningful errors instead of printing terminal output

## Key APIs
Representative APIs include:

```python
run_template(template_ref, params=None, project=None, outdir=None, pack_refs=None, binding_ref=None)
load_project(path)
init_project(path, project_id=None)
load_template(template_ref, pack_refs=None)
resolve_params(template, cli_params=None, project=None)
```

These exact names may evolve, but the shape should remain similar.

## `run_template(...)`
This is the main execution entrypoint.

It should:

- load the template
- load/discover project context if needed
- resolve parameters
- determine instance identity and output location
- execute the template
- write runtime and metadata files
- update project state when applicable
- return structured result data

For the simple ad hoc case, `pack_refs` and `binding_ref` may be used as one-off asset selectors for the current invocation.

For repeated use, project configuration should remain the primary place where per-pack binding choices are recorded. The API should not force callers to reconstruct long-lived project asset configuration on every call.

Example result shape:

```python
{
    "template": "fastqc",
    "instance_id": "fastqc_001",
    "outdir": "/path/to/project/fastqc_001",
    "meta": "/path/to/project/fastqc_001/.linkar/meta.json",
    "runtime": "/path/to/project/fastqc_001/.linkar/runtime.json",
}
```

## `load_project(path)`
Loads and validates a project from `project.yaml`.

The API should expose project state as structured data rather than leaving callers to parse YAML themselves.

## `init_project(path, project_id=None)`
Creates a minimal Linkar project.

This should be lightweight and safe to call from CLI, tests, or future service layers.

## `load_template(template_ref, pack_refs=None)`
Loads and validates a template definition from either:

- an explicit template path
- a template id resolved from one or more configured pack roots

For simplicity, the core should support a search-path style pack model before introducing more complex registry behavior.

Those pack references may come from:

- local paths
- cached Git/GitHub-backed assets
- future registry-backed assets

## `resolve_params(...)`
Resolves and validates the final parameter set before execution.

This logic should be reusable independently of full execution so it can support:

- validation
- preview/debugging
- future UI and agent flows

## Error Model
The core API should raise structured errors for:

- invalid templates
- invalid projects
- unresolved required parameters
- unsupported execution modes
- execution failures

The API should not mix semantic behavior with terminal formatting.

## Why This Matters for AI/UI
An AI agent or UI should be able to:

- inspect templates and projects
- resolve parameters
- run templates
- inspect results

without relying on shell scraping or CLI-specific behavior.

## Summary
The core API should be:

- the source of truth for Linkar behavior
- small and explicit
- reusable across interfaces
- stable enough for automation and future products
