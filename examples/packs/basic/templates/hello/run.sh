#!/usr/bin/env bash
set -euo pipefail

printf 'Hello, %s\n' "${NAME}" > "${LINKAR_RESULTS_DIR}/greeting.txt"
