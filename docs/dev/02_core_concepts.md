# Core Concepts

This document defines the small set of concepts that Linkar is built around. These concepts should stay stable and should be enough to explain most of the system.

If a new feature cannot be described in terms of these concepts, that is a sign the design may be expanding too far.

## Template
A Template is the fundamental reusable execution unit in Linkar.

It defines:

- A stable identity
- A parameter interface
- A runnable entrypoint
- Optional metadata about execution behavior

A template is a definition, not a run. It describes how one computational step should be executed when given resolved parameters.

In practice, a template is usually a directory containing:

- `linkar_template.yaml`
- A runnable script or program such as `run.sh` or `run.py`

Key properties of a template:

- It should be executable in isolation.
- It should expose a clear parameter contract.
- It should not depend on hidden project-specific assumptions.
- It should be reusable across projects.

Examples:

- `bclconvert`
- `fastqc`
- `rnaseq`

## Template Instance
A Template Instance is one concrete execution of a template.

This distinction matters. The template is the reusable definition; the instance is the actual run with:

- Resolved parameters
- A specific output directory
- Execution metadata
- Produced outputs

For example:

- Template: `fastqc`
- Instances: `fastqc_001`, `fastqc_002`

The system should treat instances as first-class run records, even if they are indexed through the project.

## Project
A Project is the local state container that connects multiple template instances over time.

Its purpose is not to define a workflow in advance. Its purpose is to record what has been run and make outputs discoverable for later runs.

A project typically contains:

- `project.yaml`
- References to past template instances
- Indexed params, outputs, and metadata paths

Responsibilities of a project:

- Track template instances
- Support lightweight chaining via prior outputs
- Provide a stable context for repeated work
- Make project history inspectable by humans and AI systems

A project is intentionally lightweight. It is an index of run state, not a database or orchestration engine.

## Pack
A Pack is a shareable collection of reusable Linkar assets.

At minimum, a pack can contain:

- Templates
- Functions
- An optional default binding profile

Packs exist to make reuse and distribution practical. A pack should be versionable, portable, and easy to consume from another repository or environment.

Typical structure:

```text
pack/
  templates/
  functions/
  linkar_pack.yaml   # optional
```

A pack is a purposeful bundle, not just a storage folder. It may collect templates that are meant to work together for a specific analytical purpose, such as a genomics toolkit.

However, a pack should not make templates non-portable. Templates remain the atomic reusable units. A pack may provide a default binding profile for convenience, but that binding should remain replaceable at the project or user level.

Packs are where domain-specific logic should live. The Linkar core should stay generic.

## Function
A Function is reusable logic invoked by Linkar to help resolve or transform execution state.

Functions are deliberately narrower than "plugins" and lighter than a full hook system. They should be used when simple declarative configuration is not enough.

Primary uses include:

- Parameter resolution
- Data binding
- Lightweight transformation
- Lifecycle assistance such as pre/post processing

Examples:

- `get_latest_fastq(ctx) -> path`
- `resolve_reference_genome(ctx) -> path`

Functions should extend the system without forcing the core to absorb domain-specific rules.

## Output
An Output is a produced artifact or location that a template instance exposes for downstream use.

Outputs are important because they form the connection surface between runs. Linkar does not primarily chain through an explicit workflow graph; it chains through recorded outputs and parameter resolution.

Outputs may include:

- Result directories
- Key files
- Derived data locations
- Named values recorded in metadata

Outputs should be explicit enough that later runs, users, and agents can consume them reliably.

## Metadata
Metadata is the structured record that explains a template instance after execution.

It should capture at least:

- Template identity
- Instance identity
- Resolved parameters
- Output locations
- Execution command
- Timestamp
- Relevant software/version information when available

Metadata exists to support reproducibility, inspection, methods generation, and AI reasoning. It is not auxiliary debug information.

## Binding
Binding is the process of mapping a parameter for a new run to a value derived from project state or function logic.

This is how Linkar enables lightweight chaining without requiring users to define an explicit DAG for every workflow.

Examples:

- `rnaseq.fastq_dir <- latest fastq_dir output in project`
- `aligner.index <- function(ctx)`

Binding should remain explicit and understandable. It should not become a source of hidden magic.

A binding may be:

- provided by a pack as its default binding
- provided separately as a facility-specific or personal overlay
- omitted entirely when templates are run with explicit parameters

Bindings are therefore pluggable overlays, not mandatory companions of every template.

## Relationships
The concepts relate as follows:

- A Pack contains Templates and Functions.
- A Pack may also provide a default Binding.
- A Template defines how one execution step works.
- A Template Instance is one execution of a Template.
- A Project indexes Template Instances over time.
- Template Instances produce Outputs and Metadata.
- Future Template runs resolve parameters from CLI input, bindings, project outputs, or defaults.

In compact form:

`Pack -> Templates / Functions / optional Binding -> Template Instance -> Outputs + Metadata -> Project index -> Next run`

## Design Boundaries
These concept definitions imply a few important boundaries:

- A template is not a workflow.
- A project is not a scheduler.
- A function is not a general plugin framework.
- A pack is not a package manager.
- A binding is not required for a template to be valid.
- Metadata is not optional bookkeeping.

Keeping these boundaries sharp is important. Linkar only stays coherent if these concepts remain small and distinct.
