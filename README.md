# linkar

`linkar` is a lightweight execution engine for reusable computational templates. The current implementation provides:

- A Python core with pure project and template orchestration logic
- A thin CLI with `linkar project init` and `linkar run`
- YAML-based templates and projects
- Metadata and runtime capture under `.linkar/`

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest
```

Initialize a project:

```bash
linkar project init ./demo --id project_001
```

Run the example template from the bundled pack:

```bash
linkar run hello \
  --pack ./examples/packs/basic \
  --project ./demo \
  --param name=Linkar
```

This creates an instance directory in the project, writes results to `results/`, and records metadata in `.linkar/meta.json`.
