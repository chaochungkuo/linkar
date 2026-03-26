# Asset Reference Model

This document defines the MVP asset reference model for packs and bindings.

The purpose of the model is to let Linkar load external assets in a simple, reproducible way without introducing a full registry system yet.

## Goals
The asset reference model should support:

- local path references
- GitHub shorthand references
- generic Git URL references
- local caching of fetched assets
- revision capture for reproducibility

## Supported Reference Forms
### Local Path
Examples:

```text
/opt/linkar/packs/genomics-pack
./facility-binding
```

Local paths are resolved directly and do not require caching.

### GitHub Shorthand
Examples:

```text
github:org/genomics-pack
github:org/genomics-pack@main
github:org/genomics-pack@v0.1.0
```

This resolves to a Git clone of:

```text
https://github.com/org/genomics-pack.git
```

with an optional revision checkout.

### Generic Git Reference
Examples:

```text
git+https://github.com/org/genomics-pack.git
git+https://github.com/org/genomics-pack.git@v0.1.0
git+file:///tmp/local-pack-repo
```

This allows non-GitHub Git sources and also local Git-based tests.

## Asset Kinds
The same reference model should apply to:

- packs
- bindings

They are loaded similarly but remain different asset types semantically.

## Resolution Rules
When an asset reference is encountered:

1. If it is a local path, resolve it directly.
2. If it is a supported remote reference, fetch it into the local cache if not already present.
3. If a revision is specified, check out that revision.
4. Record the effective revision for provenance.

## Cache Location
The MVP cache location should be:

```text
$LINKAR_HOME/assets
```

If `LINKAR_HOME` is not set, Linkar may fall back to:

```text
~/.linkar/assets
```

This keeps asset caching isolated from project directories while remaining simple.

## Cache Behavior
The MVP cache behavior should be conservative:

- fetch on first use
- reuse cached assets on later use
- do not auto-refresh silently

This makes behavior more predictable and easier to reason about during early development.

## Reproducibility
When a remote asset is used, metadata should capture:

- the original asset reference
- the resolved Git revision when available

This is important because a shorthand or branch name alone is not sufficient for durable provenance.

## Non-Goals
The MVP asset model should not yet include:

- registry accounts
- publishing workflows
- automatic background refresh
- dependency graphs between assets

## Summary
The MVP asset reference model is intentionally simple:

- path, GitHub shorthand, or generic Git
- local cache
- explicit revision capture
- no registry complexity yet
