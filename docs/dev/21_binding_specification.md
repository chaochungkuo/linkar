# Binding Specification

This document defines the MVP contract for `binding.yaml`.

The goal of the binding format is to stay small and explicit. A binding should help adapt reusable templates to a local workflow context without turning Linkar into a hidden rule engine.

## Purpose
A binding provides parameter values for a template when explicit caller input is not used.

Bindings are optional overlays. Templates must remain runnable without them when explicit parameters are supplied.

## Location
A binding asset is a directory containing:

```text
binding/
  binding.yaml
  functions/   # optional
```

A pack may also provide a default binding directly at:

```text
pack/
  binding.yaml
  functions/   # optional
```

## Structure
The MVP structure is:

```yaml
templates:
  consume_data:
    params:
      source_dir:
        template: produce_data
        output: results_dir
```

## Top-Level Fields
### `templates`
Required.

This maps template ids to template-specific binding rules.

## Template Entry
Each template entry may define:

- `params`

Example:

```yaml
templates:
  consume_data:
    params:
      source_dir:
        template: produce_data
        output: results_dir
```

## Parameter Rule
Each parameter rule should define exactly one source shape.

## Supported Rule Shapes
### Project output binding
Resolve the value from the latest output exposed by a specific template id.

Example:

```yaml
source_dir:
  template: produce_data
  output: results_dir
```

If `output` is omitted, the parameter name may be used as the default output key.

### Function binding
Resolve the value by calling a named function.

Example:

```yaml
reference_fasta:
  function: resolve_reference
```

Functions are loaded from the binding asset's `functions/` directory first, then from the selected pack's `functions/` directory if needed.

Each function file should define:

```python
def resolve(ctx):
    ...
```

### Literal value binding
Resolve the value from a literal value stored in the binding rule.

Example:

```yaml
reference_name:
  value: hg38
```

## Resolution Behavior
Bindings are applied after explicit caller input and before passive project-output fallback.

MVP precedence:

1. explicit caller input
2. binding
3. project output fallback
4. default

If a binding rule exists for a parameter and fails to resolve, the run should fail clearly rather than silently ignoring the binding.

## Default vs Override
A pack may ship a default binding at its root and also provide alternate binding assets elsewhere.

That allows a project or caller to choose between:

- the pack's default linkage behavior
- an explicit override binding for a different local context

This should remain a conscious selection by the caller or project configuration. Linkar should not silently switch between bindings based on ambient state.

## Function Context
Binding functions receive a context object that may expose:

- current template
- active project
- already resolved parameters
- helper access to latest project outputs

The context should remain explicit and small.

## Non-Goals
The MVP binding format should not support:

- complex conditional logic
- workflow branching
- hidden side-effect-heavy behavior
- remote function loading

## Summary
The MVP binding format is intentionally narrow:

- template-targeted
- parameter-focused
- explicit in source type
- small enough to validate and debug easily
