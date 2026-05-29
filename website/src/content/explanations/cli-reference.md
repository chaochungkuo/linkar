---
title: CLI reference
description: Commands, subcommands, common examples, and structured output support for the Linkar CLI.
order: 11
---

Use this page when you know the command family you need. Use the guides when you want a worked
path from a fresh project to a completed run.

Most commands accept `-h` or `--help`. Runtime and project-data commands generally support
`--format json` and `--format yaml` for automation.

## Common options

<div class="command-list command-list-compact">
  <article class="command-card">
    <h3>Help and versions</h3>
    <p>Use command-local help first; dynamic template subcommands expose the same help style.</p>
    <pre><code>linkar --help
linkar --version
linkar run --help
linkar run TEMPLATE --help</code></pre>
  </article>
  <article class="command-card">
    <h3>Structured output</h3>
    <p>Commands that report runtime or project state can emit machine-readable JSON or YAML.</p>
    <pre><code>linkar templates --format yaml
linkar project runs --format json
linkar inspect run fastqc_001 --format yaml</code></pre>
  </article>
</div>

## Execution

<div class="command-list">
  <article class="command-card">
    <h3><code>linkar run TEMPLATE</code></h3>
    <p>Execute a template. Render-mode templates reuse the visible project bundle unless <code>--refresh</code> is passed.</p>
    <pre><code>linkar run demultiplex --param run_name=HLMCNDRX7
linkar run methods --refresh</code></pre>
  </article>
  <article class="command-card">
    <h3><code>linkar render TEMPLATE</code></h3>
    <p>Stage a standalone editable bundle without executing it. The output directory must be empty or absent.</p>
    <pre><code>linkar render demultiplex --outdir ./demultiplex</code></pre>
  </article>
  <article class="command-card">
    <h3><code>linkar collect RUN_REF</code></h3>
    <p>Refresh declared outputs after manual execution.</p>
    <pre><code>linkar collect ./demultiplex
linkar collect fastqc_001 --format yaml</code></pre>
  </article>
  <article class="command-card">
    <h3><code>linkar clean [TARGET]</code></h3>
    <p>Remove template-declared disposable runtime artifacts from a project or rendered template directory, using the latest configured pack cleanup rules when available. When TARGET is omitted, Linkar cleans the current directory.</p>
    <pre><code>linkar clean --dry-run
linkar clean
linkar clean ./demultiplex --yes</code></pre>
  </article>
  <article class="command-card">
    <h3><code>linkar inspect run RUN_REF</code></h3>
    <p>Inspect recorded metadata, params, outputs, warnings, and provenance.</p>
    <pre><code>linkar inspect run fastqc_001
linkar inspect run ./fastqc --format yaml</code></pre>
  </article>
  <article class="command-card">
    <h3><code>linkar test TEMPLATE</code></h3>
    <p>Run a template-local <code>test.sh</code> or <code>test.py</code> through Linkar.</p>
    <pre><code>linkar test fastqc --pack ./examples/packs/basic</code></pre>
  </article>
</div>

Run and render share `--pack`, `--binding`, `--project`, `--outdir`, `--param KEY=VALUE`,
`--prompt/--no-prompt`, and `--format`. `run` also supports `--verbose` and `--refresh`.

## Projects

<div class="command-list">
  <article class="command-card">
    <h3><code>linkar project init</code></h3>
    <p>Create <code>project.yaml</code> in the target directory. Use <code>--adopt</code> to import existing runs while initializing.</p>
    <pre><code>linkar project init --name study
linkar project init --name study --adopt /path/to/run</code></pre>
  </article>
  <article class="command-card">
    <h3><code>linkar project runs</code></h3>
    <p>List runs recorded in <code>project.yaml</code>.</p>
    <pre><code>linkar project runs
linkar project runs --format yaml</code></pre>
  </article>
  <article class="command-card">
    <h3><code>linkar project view</code></h3>
    <p>Show project metadata and recorded runs.</p>
    <pre><code>linkar project view
linkar project view fastqc_001 --format yaml</code></pre>
  </article>
  <article class="command-card">
    <h3><code>linkar project latest RUN_REF</code></h3>
    <p>Return the newest matching recorded run.</p>
    <pre><code>linkar project latest fastqc
linkar project latest ./methods</code></pre>
  </article>
  <article class="command-card">
    <h3><code>linkar project adopt-run RUN_REF</code></h3>
    <p>Import existing Linkar run directories into the active project.</p>
    <pre><code>linkar project adopt-run /path/to/run</code></pre>
  </article>
  <article class="command-card">
    <h3><code>linkar project remove-run RUN_REF</code></h3>
    <p>Remove a run record, optionally deleting files.</p>
    <pre><code>linkar project remove-run fastqc_001
linkar project remove-run fastqc --delete-files</code></pre>
  </article>
  <article class="command-card">
    <h3><code>linkar project prune</code></h3>
    <p>Remove stale duplicate-path history.</p>
    <pre><code>linkar project prune --dry-run
linkar project prune --keep 2
linkar project prune --template methods --keep 1</code></pre>
  </article>
  <article class="command-card">
    <h3><code>linkar project author ...</code></h3>
    <p>Manage author metadata stored in <code>project.yaml</code>.</p>
    <pre><code>linkar project author show
linkar project author set --name "Project Owner"
linkar project author clear</code></pre>
  </article>
</div>

Accepted run references include instance ids, unique template ids, visible project paths, run
directory paths, and `.linkar/meta.json` paths when unambiguous.

## Packs

Project packs are saved in `project.yaml`. Global packs are saved in the user-level Linkar config.
Use project packs when a project should carry its pack setup with it. Use global packs for personal
defaults.

<div class="command-list command-list-compact">
  <article class="command-card">
    <h3>Project packs</h3>
    <p>Saved in <code>project.yaml</code>; use these when a project should carry its pack setup.</p>
    <pre><code>linkar pack add REF --id ID
linkar pack list
linkar pack use ID
linkar pack show
linkar pack status
linkar pack update ID
linkar pack update --all
linkar pack remove ID</code></pre>
  </article>
  <article class="command-card">
    <h3>Global packs</h3>
    <p>Saved in the user-level Linkar config; use these for personal defaults.</p>
    <pre><code>linkar config pack add REF --id ID
linkar config pack list
linkar config pack use ID
linkar config pack show
linkar config pack update ID
linkar config pack update --all
linkar config pack remove ID</code></pre>
  </article>
</div>

Common examples:

```bash
linkar config pack add github:IZKF-Genomics/izkf_pack --id izkf_pack
linkar config pack use izkf_pack
linkar pack add github:IZKF-Genomics/izkf_pack --id izkf_pack --binding default
linkar pack status
linkar pack update izkf_pack
```

## Discovery and automation

<div class="command-list">
  <article class="command-card">
    <h3><code>linkar templates</code></h3>
    <p>List templates visible from explicit packs and the active project configuration.</p>
    <pre><code>linkar templates
linkar templates --pack ./examples/packs/basic --format yaml</code></pre>
  </article>
  <article class="command-card">
    <h3><code>linkar serve</code></h3>
    <p>Expose the local project/runtime API over HTTP.</p>
    <pre><code>linkar serve --port 8000 --api-token local-dev:read,resolve,execute</code></pre>
  </article>
  <article class="command-card">
    <h3><code>linkar mcp serve</code></h3>
    <p>Start the stdio MCP server for agent clients.</p>
    <pre><code>linkar mcp serve</code></pre>
  </article>
  <article class="command-card">
    <h3><code>linkar completion</code></h3>
    <p>Print or install shell completion scripts for supported shells.</p>
    <pre><code>linkar completion zsh
linkar completion install zsh --yes
linkar completion install bash --rc-file ~/.bashrc
linkar completion install fish</code></pre>
  </article>
  <article class="command-card">
    <h3><code>linkar config author ...</code></h3>
    <p>Manage default author metadata for new projects.</p>
    <pre><code>linkar config author set --name "Your Name" --email "you@example.org"
linkar config author show
linkar config author clear</code></pre>
  </article>
</div>

Use `linkar templates` before `run` or `render` when you want to verify which pack and template id
will be visible from the current project context.
