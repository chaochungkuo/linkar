# Ephemeral Execution

This document defines how Linkar behaves when no project is active.

Ephemeral execution exists to support quick runs without requiring project setup. It should be convenient, but it should not weaken the core project model.

## Purpose
Ephemeral mode is useful for:

- quick experimentation
- testing templates
- one-off execution
- demo scenarios where persistent project history is unnecessary

## Behavior
If no project is found in the current directory and no explicit project is supplied, Linkar may execute in ephemeral mode.

The run should still produce:

- a run directory
- `results/`
- `.linkar/meta.json`
- `.linkar/runtime.json`

## Default Location
Ephemeral runs should be created under:

```text
.linkar/runs/
```

relative to the current working directory unless an explicit output path is provided.

## Trade-Offs
Ephemeral execution provides convenience, but with clear limitations:

- no project-level chaining
- no persistent project history
- no shared project index of prior outputs

This trade-off should remain explicit in the design.

## Relationship to Normal Project Mode
Ephemeral mode is not the primary operating model.

Project mode remains the preferred path when users want:

- repeated work
- chaining across steps
- inspectable project history
- durable context for AI or UI tooling

## Design Constraints
Ephemeral execution should:

- preserve the same run artifact structure as project mode
- avoid inventing a second execution model
- remain clearly distinct from project-backed chaining

## Summary
Ephemeral execution is a convenience mode:

- same run artifact shape
- less persistent context
- useful for quick runs
- intentionally weaker than project mode
