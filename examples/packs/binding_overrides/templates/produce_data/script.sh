#!/usr/bin/env bash
set -euo pipefail

mkdir -p "${LINKAR_RESULTS_DIR}/dataset"
printf '%s\n' "${VALUE}" > "${LINKAR_RESULTS_DIR}/dataset/sample.txt"
