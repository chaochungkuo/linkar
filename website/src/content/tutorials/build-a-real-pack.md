---
title: Build a real pack with templates and bindings
description: Create a small but realistic pack: one standalone producer template, one consumer template, and one pack-level binding that removes repeated manual wiring.
order: 3
status: ready
---

Use this tutorial when you already understand the basic CLI path and want to build a pack that
feels like real reusable work rather than a toy one-template demo.

The goal is to build three things:

- one standalone template that produces output
- one standalone template that consumes input
- one pack-level binding that links the two so the caller does not re-enter the same path again

## 1. Create the pack layout

Start with a normal pack directory:

```text
message_pack/
  linkar_pack.yaml
  templates/
    produce_message/
    consume_message/
```

The pack contract lives at the pack root in `linkar_pack.yaml`.

Each template gets its own directory and should remain runnable and testable on its own.

## 2. Add a producer template

Create `templates/produce_message/linkar_template.yaml`:

```yaml
id: produce_message
version: 0.1.0
description: Write one message into the results directory.
params:
  message:
    type: str
    required: true
outputs:
  results_dir: {}
  message_file:
    path: message.txt
run:
  command: >-
    printf '%s\n' "${param:message}" > "${LINKAR_RESULTS_DIR}/message.txt"
```

This template is intentionally small:

- explicit input param
- explicit declared output
- `run.command` because one command is enough

Add a local test at `templates/produce_message/test.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

tmpdir="$(mktemp -d)"
trap 'rm -rf "${tmpdir}"' EXIT

linkar run ./templates/produce_message --outdir "${tmpdir}" --param message=hello
test -f "${tmpdir}/results/message.txt"
grep -q '^hello$' "${tmpdir}/results/message.txt"
```

## 3. Add a consumer template

Create `templates/consume_message/linkar_template.yaml`:

```yaml
id: consume_message
version: 0.1.0
description: Read a previous message file and create a transformed result.
params:
  results_dir:
    type: path
    required: true
outputs:
  results_dir: {}
  transformed_file:
    path: transformed.txt
run:
  entry: run.sh
```

Then add `templates/consume_message/run.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

input_file="${RESULTS_DIR}/message.txt"
tr '[:lower:]' '[:upper:]' < "${input_file}" > "${LINKAR_RESULTS_DIR}/transformed.txt"
```

This template stays standalone too. It accepts one path and does one job. Nothing in the template
definition itself assumes another template exists.

Add a local test at `templates/consume_message/test.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

tmpdir="$(mktemp -d)"
trap 'rm -rf "${tmpdir}"' EXIT

mkdir -p "${tmpdir}/source"
printf 'hello\n' > "${tmpdir}/source/message.txt"

linkar run ./templates/consume_message \
  --outdir "${tmpdir}/run" \
  --param results_dir="${tmpdir}/source"

grep -q '^HELLO$' "${tmpdir}/run/results/transformed.txt"
```

## 4. Add the pack-level binding

Now connect the templates in `linkar_pack.yaml`:

```yaml
templates:
  consume_message:
    params:
      results_dir:
        template: produce_message
        output: results_dir
```

This is the pack-level chaining rule.

It means:

- `consume_message` still declares `results_dir` as a normal required input
- when the template is used through this pack binding, Linkar can resolve that input from the
  latest `produce_message` run in the project

That keeps the template reusable while still letting the pack remove repeated manual wiring.

## 5. Test the templates locally

While authoring, run the local tests from each template directory:

```bash
cd message_pack/templates/produce_message
bash test.sh
```

```bash
cd message_pack/templates/consume_message
bash test.sh
```

Then validate through Linkar itself from the pack root or repo root:

```bash
linkar test produce_message --pack ./message_pack
linkar test consume_message --pack ./message_pack --param results_dir=./some/results/dir
```

That follows the current codebase model:

- local `test.sh` or `test.py` for fast authoring feedback
- `linkar test ...` for the real runtime path

## 6. Use the pack in a project

Create a project and attach the pack with its default binding:

```bash
linkar project init --name message-demo
cd message-demo
linkar pack add ../message_pack --id message_pack --binding default
```

Now run the producer:

```bash
linkar run produce_message --message "hello from linkar"
```

Then run the consumer without manually passing `results_dir`:

```bash
linkar run consume_message
```

That is the moment when the pack starts paying off. The caller does not have to retype the output
path from the previous step, and the reusable connection lives in the pack instead of in shell
history.

## 7. Add custom binding logic only when needed

If output-to-input mapping is not enough, add a binding function:

```text
message_pack/
  linkar_pack.yaml
  functions/
    resolve_message_source.py
```

Example:

```python
from pathlib import Path


def resolve(ctx):
    latest = ctx.latest_output("results_dir", template_id="produce_message")
    if latest is None:
        raise ValueError("No produce_message run is available")
    return str(Path(latest).resolve())
```

Then reference it in `linkar_pack.yaml`:

```yaml
templates:
  consume_message:
    params:
      results_dir:
        function: resolve_message_source
```

Use this only when you need real custom resolution behavior. If a simple `template` plus `output`
rule is enough, keep the binding declarative.

## What this tutorial demonstrates

- templates remain standalone units
- packs are where reusable chaining logic belongs
- bindings reduce repeated manual parameter wiring
- the project records local runs, while the pack carries reusable behavior

That is the core Linkar model in one small pack.
