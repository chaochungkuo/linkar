---
title: Managing Git-backed packs
description: Install, update, switch, pin, and develop packs that live in GitHub or another Git remote.
order: 3
status: ready
---

Git-backed packs are the normal way to share Linkar templates beyond one machine. A template author
can develop a pack locally, push it to GitHub, and users can install or update that pack directly
from the Git ref.

This guide uses `github:IZKF-Genomics/izkf_pack` as the concrete example.

If you want the conceptual difference between `--pack`, project packs, and global packs first, read
[Using global packs vs project packs](../packs-and-scope/).

## Quick start

Register a shared pack once in your user config:

```bash
linkar config pack add github:IZKF-Genomics/izkf_pack --id izkf_pack
linkar config pack list --format yaml
linkar templates
```

After this, Linkar can find templates from that pack without passing `--pack` each time. Create a
project and run a template with the inputs it needs:

```bash
linkar project init --name study
cd study

linkar run scrna_prep \
  --input-h5ad /data/study/raw_counts.h5ad \
  --organism human \
  --binding default \
  --verbose
```

Inspect the recorded run:

```bash
linkar inspect run scrna_prep_001
```

## Update a GitHub pack

Remote packs are cached under `~/.linkar/assets/` or `$LINKAR_HOME/assets`. Linkar does not fetch on
every command. Updates are explicit so users control when a pack changes.

```bash
linkar config pack update izkf_pack
linkar config pack list --format yaml
```

The update output reports the previous and current commit revisions.

Update every configured global pack:

```bash
linkar config pack update --all
```

This is the normal day-to-day update path for a shared pack that tracks a branch.

## Use a pack for one command

Use `--pack` when you want a one-off command and do not want to modify global or project config:

```bash
linkar run scrna_prep \
  --pack github:IZKF-Genomics/izkf_pack \
  --input-h5ad /data/study/raw_counts.h5ad \
  --organism human \
  --binding default \
  --verbose
```

This is useful for trying a pack before installing it.

## Use a local checkout while developing

Template authors usually work from a local checkout:

```bash
cd ~/github
gh repo clone IZKF-Genomics/izkf_pack

linkar config pack add ~/github/izkf_pack --id izkf_pack_local
linkar config pack use izkf_pack_local
linkar config pack show
```

Run or test templates from the local checkout:

```bash
linkar test scrna_prep --pack ~/github/izkf_pack
linkar run scrna_prep \
  --pack ~/github/izkf_pack \
  --input-h5ad /path/to/input.h5ad \
  --organism human
```

## Switch between GitHub and local packs

It is common to keep both the published pack and a local development checkout configured:

```bash
linkar config pack add github:IZKF-Genomics/izkf_pack --id izkf_pack
linkar config pack add ~/github/izkf_pack --id izkf_pack_local --no-activate
```

Switch the active global pack:

```bash
linkar config pack use izkf_pack
linkar config pack use izkf_pack_local
```

## Save a pack in a project

Use project-level pack config when the project should carry its own pack choice:

```bash
linkar project init --name example_project
cd example_project

linkar pack add github:IZKF-Genomics/izkf_pack --id izkf_pack --binding default
linkar pack show
linkar pack list
linkar pack status
```

`linkar pack add` writes the resolved Git revision into `project.yaml`. Later project runs use that
locked revision, even if the cached branch or the upstream GitHub repository has moved.

Check whether the project lock is current with the latest remote state:

```bash
linkar pack status --check-remote
```

This may fetch remote Git refs into Linkar's local asset cache, but it does not change
`project.yaml`.

Include the templates exposed by each configured pack:

```bash
linkar pack status --templates --check-remote
```

With `--templates`, Linkar compares the templates in the locked project revision with the templates
in the latest checked source revision. The output marks templates as `unchanged`, `changed`,
`added`, or `removed`, and shows both the locked and latest template versions when available. This
is useful as an update preview before you move the project lock.

`linkar run ...` and `linkar render ...` also show a one-line reminder when they notice that the
remote pack has moved ahead. The command still uses the locked project revision.

Update the project-configured pack when you want the project lock to move forward:

```bash
linkar pack update izkf_pack
linkar pack list --format yaml
linkar pack status
```

Use this when a project should stay explicit about its pack source and revision instead of relying
on each user's personal global config.

## The versioning rule

Linkar treats the resolved Git revision as the pack version source of truth. Do not add a separate
pack-level version number to `linkar_pack.yaml` unless your site has a compatibility contract that
really needs it.

Use:

- branches when users should be able to fast-forward to new work
- Git tags for human-readable release points
- commit SHAs for exact provenance

`linkar config pack list --format yaml`, `linkar pack list --format yaml`, `project.yaml`, and run
metadata record the resolved commit revision.

## Pin a pack for reproducible work

For day-to-day internal work, an unpinned ref or branch is convenient:

```bash
linkar config pack add github:IZKF-Genomics/izkf_pack --id izkf_pack
linkar config pack add github:IZKF-Genomics/izkf_pack@main --id izkf_pack_main
```

For publication-grade or handover work, pin a tag or commit SHA:

```bash
linkar config pack add \
  github:IZKF-Genomics/izkf_pack@v2026.05.15 \
  --id izkf_pack_2026_05_15

linkar config pack add \
  github:IZKF-Genomics/izkf_pack@6463e5d47a6880285672deb2af95908854ed63e6 \
  --id izkf_pack_6463e5d
```

Tags are just named Git revisions. Linkar still records the resolved commit SHA.

Pin a formal project to a release tag:

```bash
linkar pack add \
  github:IZKF-Genomics/izkf_pack@v2026.05.15 \
  --id izkf_pack_2026_05_15 \
  --binding default
```

## Remove packs

Remove a global pack:

```bash
linkar config pack remove izkf_pack_local
```

Remove a project pack:

```bash
linkar pack remove izkf_pack
```

Removing a pack only changes Linkar configuration. It does not delete your GitHub repository or local
working checkout.

## Recommended patterns

For a normal user:

```bash
linkar config pack add github:IZKF-Genomics/izkf_pack --id izkf_pack
linkar config pack update izkf_pack
```

For a template author:

```bash
linkar config pack add github:IZKF-Genomics/izkf_pack --id izkf_pack
linkar config pack add ~/github/izkf_pack --id izkf_pack_local --no-activate
linkar config pack use izkf_pack_local
```

For a formal project:

```bash
linkar pack add github:IZKF-Genomics/izkf_pack@v2026.05.15 \
  --id izkf_pack_2026_05_15 \
  --binding default
```
