# Development Roadmap

This document is the practical development roadmap for Linkar.

It is intended to guide implementation and also serve as a progress tracker. Checkboxes should be updated as work is completed.

## Guiding Rule
Development should proceed from semantic foundations outward.

The order should be:

1. Make execution correct.
2. Make reuse and provenance strong.
3. Make inspection and intelligence useful.
4. Add product surfaces last.

## Phase 0: Spec Freeze and Development Baseline
### Objective
Turn the current design docs into a stable baseline for implementation.

### Checklist
- [x] Complete and align core design docs under `docs/dev`
- [x] Define the MVP boundary
- [x] Align terminology across vision, concepts, architecture, template, project, pack, binding, CLI, and API docs
- [ ] Define repository development conventions
- [ ] Add minimal example assets specifically intended for spec validation

### Exit Criteria
- [x] No major contradictions across the core docs
- [x] Implementation can begin without unresolved ambiguity in the MVP scope

## Phase 1: Core Runtime MVP
### Objective
Build the smallest correct Linkar that can execute templates reliably in project mode and ephemeral mode.

### Scope Checklist
- [x] Support local template loading by explicit path
- [x] Implement project initialization
- [x] Implement current-directory project discovery
- [x] Implement parameter parsing and validation
- [x] Implement parameter resolution from explicit input
- [x] Implement parameter resolution from project outputs
- [x] Implement parameter resolution from defaults
- [x] Support direct execution mode
- [x] Prepare run directory layout automatically
- [x] Capture runtime information in `.linkar/runtime.json`
- [x] Capture metadata in `.linkar/meta.json`
- [x] Index successful runs in `project.yaml`
- [x] Support ephemeral execution under `.linkar/runs/`

### Deliverables Checklist
- [x] `linkar project init`
- [x] `linkar run`
- [x] `init_project`
- [x] `load_project`
- [x] `load_template`
- [x] `resolve_params`
- [x] `run_template`
- [x] Template validation
- [x] Project validation

### Validation Checklist
- [x] A standalone template can run with explicit params only
- [x] A project can record multiple instances
- [x] Project recency-based output reuse works
- [x] Failed runs preserve runtime diagnostics
- [x] CLI behavior matches core semantics

### Explicit Deferrals
- [ ] Do not add binding support in this phase
- [ ] Do not add pack loading by URL in this phase
- [ ] Do not add registry support in this phase
- [ ] Do not add API server behavior in this phase
- [ ] Do not add methods generation in this phase

### Exit Criteria
- [x] Linkar can run a small local multi-step workflow correctly using only local templates and project state

## Phase 2: Local Pack Loading
### Objective
Make reusable template collections practical without increasing semantic complexity.

### Scope Checklist
- [x] Support pack loading from local filesystem paths
- [x] Support template lookup by template id across one or more pack roots
- [x] Support optional project-level `packs:` configuration

### Deliverables Checklist
- [x] Pack search-path behavior in the core
- [x] CLI support for ad hoc `--pack`
- [x] Project-level `packs:` support in `project.yaml`
- [x] Clear error behavior when templates are missing across packs
- [x] Clear error behavior when templates are ambiguous across packs

### Validation Checklist
- [x] A template can be loaded by explicit path
- [x] A template can be loaded by template id via pack lookup
- [x] Project-level pack configuration removes the need for repeated `--pack`
- [x] Template loading remains deterministic

### Explicit Deferrals
- [ ] Do not add GitHub fetching in this phase
- [ ] Do not add binding overlays in this phase
- [ ] Do not add caching in this phase
- [ ] Do not add registry behavior in this phase

### Exit Criteria
- [x] Users can configure packs once and run templates from them repeatedly in a project

## Phase 3: Binding MVP
### Objective
Add the smallest useful binding system without breaking template portability.

### Scope Checklist
- [x] Define `binding.yaml`
- [x] Implement pack-provided default binding
- [x] Implement optional ad hoc binding selection
- [x] Implement project-level per-pack binding choice
- [x] Implement function-backed parameter resolution

### Deliverables Checklist
- [x] Binding specification document
- [x] Binding parser
- [x] Binding validator
- [x] Function loading mechanism
- [x] Resolution support for explicit caller input
- [x] Resolution support for selected binding
- [x] Resolution support for project outputs
- [x] Resolution support for defaults
- [x] CLI support for ad hoc `--binding`
- [x] Project config support for per-pack binding choice

### Validation Checklist
- [x] Templates remain runnable without binding when explicit params are supplied
- [x] A pack can ship a default binding
- [x] A project can override that default binding
- [x] Binding behavior remains deterministic
- [x] Binding behavior remains inspectable

### Explicit Deferrals
- [ ] Do not add side-effect-heavy lifecycle hooks in this phase
- [ ] Do not add a general plugin system in this phase
- [ ] Do not add remote binding registry behavior in this phase

### Exit Criteria
- [x] One pack can be used with either its default binding or a project-selected override without changing the templates

## Phase 4: Provenance Upgrade
### Objective
Strengthen reproducibility and traceability so Linkar artifacts are more durable and explainable.

### Scope Checklist
- [x] Enrich metadata design
- [x] Clarify output exposure discipline
- [x] Capture parameter provenance
- [x] Capture pack identity/version where available
- [x] Improve runtime records

### Deliverables Checklist
- [x] Enhanced `meta.json`
- [x] Parameter provenance model
- [x] Pack reference capture in metadata
- [x] Clear distinction between files present in `results/` and named outputs exposed for chaining

### Validation Checklist
- [x] Users can explain where each important parameter came from
- [x] Runs are easier to inspect and compare
- [x] Pack usage is visible in provenance

### Explicit Deferrals
- [ ] Do not add full environment manager integration in this phase
- [ ] Do not add heavyweight metadata schema versioning in this phase

### Exit Criteria
- [x] Linkar artifacts are strong enough to support reproducibility discussions and later methods generation

## Phase 5: Remote Asset Loading
### Objective
Allow packs and bindings to be loaded from remote references while keeping the model simple.

### Scope Checklist
- [x] Support Git/GitHub-based asset references
- [x] Add local caching of fetched assets
- [x] Define asset resolution lifecycle
- [x] Capture pinning or revision information

### Deliverables Checklist
- [x] Asset reference model
- [x] Path-or-Git loading support for packs
- [x] Path-or-Git loading support for bindings
- [x] Local cache location
- [x] Cache refresh behavior
- [x] Provenance capture for remote asset revision

### Validation Checklist
- [x] Users can configure packs by local path or GitHub reference
- [x] Users can configure bindings by local path or GitHub reference
- [x] Fetched assets are cached predictably
- [x] Metadata records enough information to make remote assets reproducible

### Explicit Deferrals
- [ ] Do not add registry account systems in this phase
- [ ] Do not add Docker-like distribution in this phase

### Exit Criteria
- [x] Projects can reuse external packs and bindings reproducibly without repeated manual setup

## Phase 6: Inspection and Utility Layer
### Objective
Make Linkar easier to inspect and operate once the runtime semantics are stable.

### Scope Checklist
- [x] Add project inspection helpers
- [x] Add template inspection helpers
- [x] Add metadata inspection tools
- [x] Add output browsing and traceability helpers

### Deliverables Checklist
- [x] Ability to list project runs
- [x] Ability to inspect run metadata
- [x] Ability to inspect resolved outputs
- [x] Ability to inspect available templates from configured packs

### Validation Checklist
- [x] Users can answer common inspection questions without manually opening YAML and JSON files each time
- [x] Inspection helpers remain thin over the core data model

### Explicit Deferrals
- [ ] Do not add web UI in this phase
- [ ] Do not add authenticated API server behavior in this phase

### Exit Criteria
- [x] Linkar is operationally inspectable without adding product-level complexity

## Phase 7: Methods Generation
### Objective
Turn structured provenance into useful narrative outputs.

### Scope Checklist
- [x] Aggregate `meta.json` across a project
- [x] Extract methods-oriented tool/version/parameter facts
- [x] Produce editable narrative output

### Deliverables Checklist
- [x] Methods generation command or core helper
- [x] Ordered run aggregation logic
- [x] Grounded methods text generation from metadata

### Validation Checklist
- [x] Generated methods text is traceable back to metadata
- [x] Metadata gaps remain visible instead of being hallucinated away

### Explicit Deferrals
- [ ] Do not build a generic free-form report writer in this phase
- [ ] Do not replace metadata with prose in this phase

### Exit Criteria
- [x] A project can generate a useful first-pass methods summary from recorded runs

## Phase 8: API and Agent Readiness
### Objective
Make the core robust enough to support non-CLI consumers cleanly.

### Scope Checklist
- [x] Strengthen structured core return values
- [x] Standardize error types
- [x] Add inspection-oriented API helpers
- [x] Plan a thin external API/server direction

### Deliverables Checklist
- [x] Stable core API contract
- [x] Clearer error model
- [x] `list_templates(...)` or equivalent helper
- [x] `inspect_run(...)` or equivalent helper
- [x] `resolve_project_assets(...)` or equivalent helper
- [x] Separate future API/server direction doc if needed

### Validation Checklist
- [x] An AI agent can use the core without shell scraping
- [x] The CLI remains a frontend over the same semantics

### Explicit Deferrals
- [ ] Do not build a multi-user system in this phase
- [ ] Do not build auth/authz infrastructure in this phase
- [ ] Do not build job queue behavior in this phase

### Exit Criteria
- [x] The core is ready to be wrapped by an API server without semantic redesign

## Phase 9: Local API Server MVP
### Objective
Add a thin local API server over the stable core so non-CLI consumers can integrate without shell scraping.

### Scope Checklist
- [x] Expose health and readiness endpoint
- [x] Expose template listing endpoint
- [x] Expose project run listing endpoint
- [x] Expose project asset inspection endpoint
- [x] Expose run inspection endpoint
- [x] Expose methods generation endpoint
- [x] Expose template execution endpoint
- [x] Add a CLI entrypoint for serving the API locally
- [x] Map typed core errors to stable JSON responses

### Deliverables Checklist
- [x] `linkar serve`
- [x] Thin WSGI app over the current core helpers
- [x] Stable JSON response shape for the MVP endpoints
- [x] Focused tests for server behavior and error mapping

### Validation Checklist
- [x] The API server mirrors core semantics rather than redefining them
- [x] An external consumer can inspect templates, runs, assets, and methods without shell parsing
- [x] An external consumer can trigger local execution through the same runtime path used by the CLI

### Explicit Deferrals
- [ ] Do not add authentication or authorization in this phase
- [ ] Do not add multi-user state in this phase
- [ ] Do not add job queue or remote execution behavior in this phase
- [ ] Do not move domain logic into the server layer in this phase

### Exit Criteria
- [x] Linkar can be used locally through either the CLI or a thin JSON API without semantic drift

## Phase 10: Registry and Product Layer
### Objective
Add broader distribution and richer user-facing surfaces after the local API layer is proven.

### Scope Checklist
- [ ] Define template or asset registry architecture
- [ ] Add richer pack discovery
- [ ] Add web dashboard direction
- [ ] Add collaboration-oriented product features

### Deliverables Checklist
- [ ] Registry architecture
- [ ] Discovery UX
- [ ] UI or service features built on top of the stable core

### Validation Checklist
- [ ] Product layers mirror core semantics rather than redefining them
- [ ] Distributed assets remain reproducible and inspectable

### Explicit Deferrals
- [ ] Do not reinvent the execution model in this phase
- [ ] Do not push domain logic into a service layer in this phase

### Exit Criteria
- [ ] Product surfaces add convenience without introducing conceptual instability

## Cross-Cutting Workstreams
### Testing
- [ ] Add unit tests for parsers and resolution logic
- [ ] Add integration tests for template execution
- [ ] Add project-mode coverage
- [ ] Add ephemeral-mode coverage
- [ ] Add pack selection tests once pack support exists
- [ ] Add binding selection tests once binding support exists
- [x] Add API server tests once the local API layer exists

### Documentation
- [ ] Keep `docs/dev` aligned with implementation
- [ ] Maintain example templates and packs
- [ ] Write minimal user-facing quickstarts when behavior stabilizes

### Example Assets
- [ ] Maintain one minimal standalone template
- [ ] Maintain one small multi-step pack
- [ ] Maintain one example binding setup showing default vs override behavior

### Error Quality
- [ ] Improve early validation errors
- [ ] Improve deterministic ambiguity handling
- [ ] Improve missing asset error messages
- [ ] Improve missing parameter error messages
- [ ] Improve failed run error messages

## Recommended Immediate Build Order
- [ ] Finish Phase 1 completely before adding richer reuse layers
- [ ] Add only local path-based pack loading from Phase 2 first
- [ ] Define `binding.yaml` before implementing runtime binding behavior
- [ ] Add the smallest binding MVP from Phase 3
- [ ] Strengthen provenance before remote asset loading
- [ ] Add Git/GitHub asset loading only after the above are stable

## Explicit Long-Term Deferrals
- [ ] Defer registry or Docker-Hub-like distribution until later
- [ ] Defer web UI until the core is ready
- [ ] Defer remote execution until much later
- [ ] Defer distributed scheduling
- [ ] Defer large plugin surfaces
- [ ] Defer complicated workflow syntax

## Definition of Success
- [ ] Linkar remains conceptually small
- [ ] Templates remain standalone and portable
- [ ] Packs improve reuse without reducing portability
- [ ] Bindings improve convenience without becoming hidden magic
- [ ] Project state stays transparent
- [ ] Metadata becomes trustworthy enough for reproducibility and methods generation
- [ ] Future APIs and UIs can be layered on without changing core semantics
