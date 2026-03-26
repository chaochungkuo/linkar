# Parameter Resolution

This document defines how Linkar determines the final value for each template parameter before execution.

Resolution is one of the most important parts of the system because it is where explicit user intent, reusable project context, and lightweight automation come together.

## Goal
The goal of parameter resolution is to produce one final, validated value for each declared parameter before the template runs.

Resolution should be:

- deterministic
- explainable
- easy to inspect afterward
- consistent across CLI and API use

## Resolution Priority
The default resolution order is:

1. Explicit caller input
2. Binding or function-derived value
3. Matching project output
4. Template default
5. Error if still unresolved and required

This priority keeps the system intuitive:

- explicit user intent wins
- configured linkage beats passive inference
- project history provides convenient fallback
- defaults are last-resort convenience

## Resolution Inputs
The resolution subsystem may draw from:

- parameters supplied by CLI or API
- binding definitions attached to the template or pack
- previously recorded outputs in the active project
- defaults declared in `template.yaml`

Each source should be inspectable. Resolution should not depend on hidden ambient state.

## Project Dependency
Project-derived resolution only applies when a project is active.

If no project is present:

- explicit caller input still works
- defaults still work
- binding behavior may work if it does not depend on project state
- project-output fallback is unavailable

This is one of the main trade-offs of ephemeral execution.

## Resolution Algorithm
Pseudo-code:

```python
for key, spec in template.params.items():
    if key in explicit_input:
        use(explicit_input[key], source="cli_or_api")
    elif binding_exists(key):
        use(call_binding(key, ctx), source="binding")
    elif project_has_matching_output(key):
        use(latest_project_output(key), source="project")
    elif spec_has_default(key):
        use(default_value(key), source="default")
    elif is_required(key):
        fail(key)
    else:
        omit(key)
```

The core should also record, directly or indirectly, enough information to explain where a resolved value came from.

## Caller Input
Caller input is the highest-precedence source.

This includes:

- `--param key=value` on the CLI
- direct argument values in the API

If a user provides a value explicitly, Linkar should not silently override it through project history or bindings.

## Binding Resolution
Bindings provide explicit logic for deriving parameter values.

Bindings should be used when:

- a parameter needs transformation rather than a direct lookup
- project state alone is not enough
- pack-defined reusable resolution logic is needed

Examples:

- resolve `reference_fasta` from a pack function
- choose the latest output matching a specific template type

Bindings should remain understandable and should not become a general hidden execution system.

## Project Output Resolution
If no explicit value or binding applies, the resolution system may search project history for a matching output.

Typical model:

- scan recorded template instances in reverse order
- find the most recent output matching the requested parameter name
- use that value as the fallback

This keeps chaining lightweight while preserving predictability through recency.

## Defaults
Defaults are applied only after higher-precedence sources fail to provide a value.

Defaults should be treated as stable fallback behavior, not as implicit project wiring.

## Type Coercion
After a value is selected, the core should coerce it to the declared parameter type.

This step should:

- validate compatibility
- normalize the internal representation
- fail clearly if coercion is impossible

Examples:

- `"8"` -> `8` for `int`
- `"true"` -> `True` for `bool`
- `"./data"` -> normalized path for `path`

## Missing Values
If a required parameter remains unresolved after all sources are checked, the run must fail before execution.

This is preferable to:

- silently omitting the parameter
- allowing the template to fail later with a vague shell error
- guessing based on unrelated state

## Traceability
Resolution should be explainable after the fact.

At minimum, Linkar should preserve:

- the final resolved values
- the fact that resolution happened before execution

In later versions, Linkar may also record resolution provenance in more detail, such as whether a value came from CLI, binding, project, or default.

## Design Constraints
Resolution should avoid:

- multi-step hidden fallbacks that are hard to reason about
- ambiguous matching rules across unrelated outputs
- domain-specific logic embedded directly in the core
- behavior that differs between CLI and API callers

## Summary
Linkar parameter resolution should be:

- explicit in precedence
- deterministic in output
- validated before execution
- lightweight enough for everyday chaining
- transparent enough for users and AI systems to reason about
