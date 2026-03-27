# linkar

`linkar` is a lightweight execution engine for reusable computational templates. The current implementation provides:

- A Python core with pure project and template orchestration logic
- A Click-based CLI with template-aware run commands
- YAML-based templates and projects
- Metadata and runtime capture under `.linkar/`

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest
```

Or with `pixi`:

```bash
pixi run test
pixi run cli-help
pixi run serve
```

Initialize a project:

```bash
linkar project init --name demo
```

Run the example template ad hoc from the bundled pack:

```bash
linkar run raw hello \
  --pack ./examples/packs/basic \
  --param name=Linkar
```

If a pack is configured in `project.yaml`, Linkar exposes template parameters as real CLI options:

```bash
linkar run hello --name Linkar
```

This creates an instance directory in the project, writes results to `results/`, and records metadata in `.linkar/meta.json`. Use `linkar run raw ...` when you want the generic path-or-pack execution interface.
