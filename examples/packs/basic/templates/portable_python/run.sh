#!/usr/bin/env bash
set -euo pipefail

python_cmd=""
if command -v python3 >/dev/null 2>&1; then
  python_cmd="python3"
elif command -v python >/dev/null 2>&1; then
  python_cmd="python"
else
  printf 'No python interpreter found\n' >&2
  exit 1
fi

"${python_cmd}" -c 'import os, pathlib; pathlib.Path(os.environ["LINKAR_RESULTS_DIR"]).mkdir(parents=True, exist_ok=True); pathlib.Path(os.environ["LINKAR_RESULTS_DIR"], "greeting.txt").write_text("Hello from {}\n".format(os.environ["NAME"]), encoding="utf-8")'
