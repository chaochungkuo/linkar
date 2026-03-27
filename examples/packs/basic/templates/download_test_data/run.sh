#!/usr/bin/env bash
set -euo pipefail

python - <<'PY'
from pathlib import Path
from urllib.request import urlopen
import os

source_url = os.environ["SOURCE_URL"]
output_name = os.environ["OUTPUT_NAME"]
results_dir = Path(os.environ["LINKAR_RESULTS_DIR"])
results_dir.mkdir(parents=True, exist_ok=True)

with urlopen(source_url) as response:
    payload = response.read()

(results_dir / output_name).write_bytes(payload)
PY
