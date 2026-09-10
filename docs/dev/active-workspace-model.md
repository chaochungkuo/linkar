# Active Workspace Model

This document plans the next project UX change for Linkar.

## Motivation

The current project model can record multiple entries for the same template id
when a template is rendered into different output directories. That is useful
for explicit run history, but it is noisy for project templates that represent
workflow stages such as `nfcore_3mrnaseq`, `dgea`, or `scrna_prep`.

For day-to-day project work, the common expectation should be:

```text
one project + one template id = one active workspace
```

Rerendering the same template should update the existing workspace and
`project.yaml` entry by default instead of appending another run record.

## Target UX

Default project render:

```bash
linkar render TEMPLATE
```

Behavior:

- resolves the active project
- uses `<project>/<template_id>` as the visible workspace unless an existing
  active entry records another visible path
- prompts before overwriting a non-empty existing workspace
- refreshes the project-central `.linkar/meta/<instance_id>.json`
- updates the existing `project.yaml` entry for that template id
- does not create a new project entry only because params changed

Confirmation text should be explicit:

```text
Template nfcore_3mrnaseq already exists at ./nfcore_3mrnaseq.

Rerendering will update the workspace files and project.yaml params.
Results and manually generated outputs are preserved unless the template render
step itself overwrites them.

Continue? [y/N]
```

Non-interactive flags:

- `--yes`: accept overwrite/update prompts
- `--fresh`: delete and recreate the active workspace after confirmation
- `--new-instance`: intentionally create another recorded instance
- `--outdir PATH`: render to an explicit path; in project mode this should not
  become the active canonical template entry unless paired with `--adopt` or
  `--new-instance`

## Project Ledger Rules

By default, `project.yaml` should keep one active entry per template id.

Replacement should match in this order:

1. same `instance_id`
2. same `id` and active workspace path
3. same `id` when only one entry exists for that template id
4. otherwise ask the user which existing entry to replace, or require
   `--new-instance`

Temporary output directories under `/tmp` should not be registered as canonical
project entries by default.

## `.linkar` Policy

Do not remove `.linkar` entirely.

Keep one project-root `.linkar` for:

- `meta/<instance_id>.json`
- `runtime/<instance_id>.json`
- parameter provenance
- collected outputs
- warnings and command metadata

Standalone artifacts keep `.linkar/meta.json` and `.linkar/runtime.json` for portability. Readers
must continue accepting that layout in existing projects.

But keep hidden history optional:

- the default project path should be the visible workspace
- `.linkar/runs/...` history should be created only for explicit history,
  direct-run templates that need separate executed artifacts, or
  `--new-instance`

## Implementation Phases

1. Add an active-entry resolver.
   It should find the current project entry for a template id and return the
   visible workspace, meta path, and ambiguity status.

2. Change project render defaults.
   `linkar render TEMPLATE` inside a project should target the active workspace
   and replace the existing entry by template id unless `--new-instance` is set.

3. Add confirmation and flags.
   Introduce `--yes`, `--fresh`, and `--new-instance` for render. Reuse the
   existing terminal confirmation style from cleanup/prune.

4. Adjust `run` for render-mode templates.
   `linkar run TEMPLATE --refresh` should use the same active-workspace
   replacement logic.

5. Make ad hoc renders non-canonical.
   Rendering to a temporary or explicit external path should remain possible,
   but should not silently become the newest project template entry.

6. Update API/MCP semantics.
   The local API and MCP render tools should expose the same flags and return a
   `confirmation` object when an overwrite or ambiguity decision is required.

7. Update prune messaging.
   `project prune` remains useful for older projects and explicit histories, but
   it should no longer be necessary for the common rerender path.

8. Add tests.
   Cover rerender replacement, confirmation behavior, `--new-instance`,
   external `--outdir`, and render-mode `run --refresh`.

## Migration Behavior

Existing projects with duplicate template entries should not be rewritten
automatically.

When Linkar sees duplicate entries for a template id, it should:

- prefer the entry whose visible path exists in the project
- warn if multiple candidates remain
- suggest `linkar project prune --template TEMPLATE --dry-run`
- require explicit selection or `--new-instance` when replacement is ambiguous
