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

Run the example template ad hoc from the bundled pack, without creating or using a project:

```bash
linkar run raw simple_echo \
  --pack ./examples/packs/basic \
  --param name=Linkar
```

If a pack is saved in `project.yaml`, Linkar exposes template parameters as real CLI options:

```bash
linkar pack add ./examples/packs/basic --id basic
linkar run simple_echo --name Linkar
```

In project mode, Linkar creates an instance directory in the project, writes results to `results/`, and records metadata in `.linkar/meta.json`.

Pack scope is intentionally project-first:

- `linkar run raw ... --pack ...` is ad hoc and does not require a project
- `linkar pack ...` manages packs saved in the current project's `project.yaml`
- `linkar config pack ...` manages global packs saved in user config

Pack lookup precedence is:

1. explicit `--pack`
2. project-configured packs
3. global/user-configured packs

Example global setup:

```bash
linkar config pack add ~/github/izkf_genomics_pack --id izkf_genomics_pack
linkar config pack list
linkar run fastqc --input sample.fastq.gz
```

Use `linkar run raw ...` when you want the generic path-or-pack execution interface.

## Website

The demo/docs site now lives in `website/` and is built with Astro for GitHub Pages.

Use Node 22 there:

```bash
cd website
npm install
npm run dev
```

The GitHub Pages workflow is in `.github/workflows/deploy-pages.yml`.
