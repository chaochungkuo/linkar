# Linkar Agent Notes

This file is for AI agents working in this repository.

## Required Workflow

- Do `git add` and `git commit` after every completed implementation or fix.
- Do not leave finished work uncommitted.
- If a step is incomplete or broken, fix it before committing or clearly stop at the blocker.
- Run tests or builds whenever they are practical for the change.

## Website Sync Rule

- Keep [website](/Users/jovesus/github/linkar/website) in sync with the product.
- Update the website whenever any command, syntax, mechanism, behavior, workflow, or mental model changes.
- Update tutorials, quickstart examples, and explanations when CLI or runtime behavior changes.
- If a change affects user expectations, the website must reflect it in the same stage or immediately after.

## GitHub Pages

- The website is built with Astro, not Jekyll.
- GitHub Pages is deployed through [.github/workflows/deploy-pages.yml](/Users/jovesus/github/linkar/.github/workflows/deploy-pages.yml).
- Local website work should use Node 22.
- Preferred local website validation:
  - `cd website`
  - `npx -y node@22 /opt/homebrew/lib/node_modules/npm/bin/npm-cli.js run build`

## Product Model

- Keep Linkar small.
- Do not drift into a generic workflow engine or DAG platform.
- Templates are atomic and reusable.
- Packs are curated collections of templates and optional binding defaults.
- Projects are readable local run indexes, not hidden databases or workflow definitions.

## Template Conventions

- Prefer `script.sh` as the template source script for shell-based templates.
- Render `run.sh` into the run directory as the user-facing runnable artifact.
- A rendered run directory should stay understandable without Linkar.
- Template-local testing should remain easy for pack authors.

## CLI and UX

- Keep the common path short and readable.
- Prefer current-directory project discovery over noisy required flags.
- Improve help text, examples, and output formatting when behavior changes.
- If a command becomes confusing, fix the wording, not just the implementation.

## Documentation

- Keep docs in [docs/dev](/Users/jovesus/github/linkar/docs/dev) aligned with implementation when semantics change.
- Keep [README.md](/Users/jovesus/github/linkar/README.md) aligned with the main user path.
- Do not let stale examples remain after behavior changes.

## Validation

- For Python changes, prefer `pixi run test` when possible.
- For focused fixes, run the narrowest meaningful test first, then broader validation if needed.
- For website changes, run the Astro build.
- Mention clearly when validation could not be run.

## Repo Hygiene

- Keep files small and split large modules when readability suffers.
- Preserve stable public behavior unless intentionally changing it.
- Avoid unnecessary framework churn.
- Prefer explicit, readable behavior over hidden magic.

## Separate Repositories

- `linkar` is the engine and website repo.
- External pack repos may not be git repos yet.
- Do not claim external pack changes were committed unless that repo is actually initialized and committed.
