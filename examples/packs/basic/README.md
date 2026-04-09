# Basic Example Pack

This pack contains the smallest Linkar templates intended to teach one idea at a time.

Suggested order:

1. `simple_echo`
2. `simple_file_input`
3. `simple_boolean_flag`
4. `download_test_data`
5. `fastq_stats`
6. `glob_reports`
7. `portable_python`
8. `pixi_echo`
9. `pixi_pytest`

Most templates keep the same shape:

- `linkar_template.yaml`
- `run.sh`
- `test.sh` or `test.py`
- optional support files or `testdata/`

The smallest example, `simple_echo`, now uses `run.command` directly in `linkar_template.yaml` so
the pack shows both authoring styles:

- `run.command` for thin one-command wrappers
- `run.sh` when real script logic is needed

Additional examples cover:

- declared `glob` outputs via `glob_reports`
- `tools.required_any` via `portable_python`

To stage a runnable bundle without executing it, use:

```bash
linkar render simple_echo --pack ./examples/packs/basic --param name=Linkar --outdir ./simple_echo_bundle
```
