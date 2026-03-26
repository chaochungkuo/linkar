# Methods Generation

This document describes the role of methods generation in Linkar.

Methods generation is a downstream capability built on top of Linkar metadata. It is not part of the core execution path, but it is an important reason for capturing structured metadata well.

## Goal
Generate publication-ready or report-ready methods text from recorded run metadata.

The system should help transform structured execution records into human-usable prose without requiring users to manually reconstruct every step.

## Inputs
Methods generation should consume:

- `meta.json` records across one project
- possibly selected subsets of template instances
- software/version information
- parameter values relevant to scientific or technical reporting

It should rely on structured metadata, not on ad hoc log parsing.

## Outputs
The output may include:

- publication-ready methods paragraphs
- report-ready summaries
- step-by-step protocol descriptions
- provenance summaries for internal documentation

## Non-Goal
Methods generation should not become a substitute for metadata capture.

If metadata is weak, methods generation should expose that weakness rather than hide it behind hallucinated prose.

## Likely Workflow
1. Aggregate metadata across a project.
2. Identify the relevant ordered template instances.
3. Extract software versions, key parameters, and output context.
4. Render a narrative description using template-aware phrasing rules.
5. Present editable text to the user or downstream system.

## Example
Example output:

> We processed BCL files using bcl-convert (vX), performed quality control with FastQC (vY), and quantified RNA-seq libraries using tool Z with the parameters recorded in the project metadata.

## Design Constraints
Methods generation should:

- depend on structured run metadata
- preserve factual grounding
- make uncertain or missing details visible
- remain optional and layered above the core

## Summary
Methods generation is a high-value downstream feature that depends directly on the quality of Linkar metadata and project history.
