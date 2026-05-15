# Remote Example Pack

This pack is intentionally tiny so it can be referenced over Git without extra setup.

Linkar uses the resolved Git revision as the pack version source of truth. Do
not add a separate pack-level version unless your workflow has a specific
compatibility contract that needs it.

Use it to demonstrate:

- `git+` or GitHub-based pack references
- local asset caching under `LINKAR_HOME/assets`
- provenance recording of remote revisions
- explicit cache updates with `linkar config pack update` or `linkar pack update`

Example:

```bash
linkar config pack add github:ORG/remote-pack --id remote_pack
linkar templates
linkar config pack update remote_pack
```

For project-scoped use:

```bash
linkar pack add github:ORG/remote-pack --id remote_pack
linkar pack update remote_pack
```
