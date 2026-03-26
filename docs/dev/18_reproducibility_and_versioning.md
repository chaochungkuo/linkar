# Reproducibility and Versioning

This document defines what Linkar should capture to support reproducibility.

Reproducibility is not a secondary feature. It is one of the core reasons Linkar exists instead of users simply running ad hoc scripts.

## Reproducibility Goals
A Linkar run should leave behind enough information to answer:

- what template ran
- which parameters were used
- what outputs were produced
- which software versions were involved
- when the run happened

## Minimum Capture
At minimum, Linkar should capture:

- template identity
- instance identity
- resolved parameters
- parameter provenance
- output locations
- execution command
- timestamp
- software versions when available

## Storage Location
The primary storage location is:

```text
outdir/.linkar/meta.json
```

Additional runtime execution details may live in:

```text
outdir/.linkar/runtime.json
```

## Software Version Capture
Version capture should include, where practical:

- Linkar version
- key tool versions used by the template
- pack reference and version or revision when available
- binding reference and revision when available
- environment identifiers or manager metadata in future versions

This does not mean Linkar becomes an environment manager. It means the run record should preserve enough context to interpret results later.

## Environment Snapshot
An environment snapshot may be supported in future versions, but it should remain optional.

Examples:

- selected environment variables
- package manager lock references
- Pixi/Conda environment identity

This information should supplement metadata, not overwhelm it.

## Versioning Scope
Different layers may have different version identities:

- Linkar version
- pack version or Git revision
- template version as implied by its source tree state
- binding reference or revision when relevant
- underlying domain tool versions

Later versions of the spec may define stronger conventions here, especially for packs.

## Design Constraints
Reproducibility support should:

- rely on structured metadata
- avoid requiring external services
- remain useful even when a project is moved
- favor explicit recorded facts over inferred reconstruction

## Summary
Linkar reproducibility depends on disciplined metadata capture:

- capture the run facts
- capture where resolved values came from
- capture the relevant versions
- keep the record local to the artifact
- make later inspection straightforward
