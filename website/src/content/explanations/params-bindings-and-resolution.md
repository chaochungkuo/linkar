---
title: Params, bindings, and resolution
description: How Linkar resolves values, what bindings are for, and how warnings and placeholders fit into the model.
order: 4
---

Parameter resolution is where Linkar turns a reusable template contract into one concrete run.

## Resolution order

Today Linkar resolves parameters in this order:

1. explicit CLI or API values
2. pack binding rules
3. latest matching project outputs
4. template defaults
5. missing required parameter error

That means bindings are not a sidecar convenience. They are part of the runtime contract.

## Pack bindings

The canonical pack binding file is `linkar_pack.yaml`. Linkar still accepts `binding.yaml` for
backward compatibility, but new packs should use `linkar_pack.yaml`.

Example:

```yaml
templates:
  nfcore_3mrnaseq:
    params:
      samplesheet:
        function: generate_nfcore_rnaseq_samplesheet_forward
      genome:
        function: get_agendo_genome
```

Bindings can currently resolve values through:

- `function`
- another template's `output`
- literal `value`

## Binding functions

A binding function is a small Python file in `functions/` with:

```python
def resolve(ctx):
    ...
```

The context exposes:

- `ctx.template`
- `ctx.project`
- `ctx.resolved_params`
- `ctx.latest_output(...)`
- `ctx.warn(...)`

Binding functions should stay narrow. They are best for:

- resolving a file path from another recorded run
- loading facility metadata
- deriving small defaults
- warning and returning a placeholder when render should continue

They should not turn into a second workflow engine.

## Resolution is order-sensitive

Bindings only see parameters already resolved earlier in the template.

That means parameter order in `linkar_template.yaml` matters when one binding depends on another
resolved value.

Example:

- `agendo_id` must appear before `genome` if the `genome` binding reads `ctx.resolved_params["agendo_id"]`

This is current behavior, not an abstract principle.

## Structured warnings

Bindings can emit warnings without aborting resolution:

```python
ctx.warn(
    "Could not derive genome from Agendo organism 'other'.",
    action="Edit run.sh and replace __EDIT_ME_GENOME__ before execution.",
    fallback="__EDIT_ME_GENOME__",
)
return "__EDIT_ME_GENOME__"
```

Linkar then:

- shows the warning in CLI output
- records it in `.linkar/meta.json`
- records it in `.linkar/runtime.json`

This is the preferred way to handle “render now, fix later” cases.

## Placeholders

When render should succeed but the final execution still needs human review, use a visible
placeholder such as:

```text
__EDIT_ME_GENOME__
```

That placeholder should also be enforced in the rendered script so execution fails clearly until it
is replaced.

## File localization during render

When a bound `path` or `list[path]` value points to an external file, `linkar render ...` copies it
into the rendered directory and rewrites the resolved value to the local copy.

If a staged template file already has the same basename, the localized bound file overwrites it.

That is why a rendered `samplesheet.csv` can replace a bundled fallback file cleanly.
