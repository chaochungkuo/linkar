#!/usr/bin/env bash
set -euo pipefail

export NAME="Linkar"
export LINKAR_RESULTS_DIR="${LINKAR_TEST_DIR}/results"

mkdir -p "${LINKAR_RESULTS_DIR}"

"${LINKAR_TEMPLATE_DIR}/run.sh"

test -f "${LINKAR_RESULTS_DIR}/greeting.txt"
grep -q "Hello, Linkar" "${LINKAR_RESULTS_DIR}/greeting.txt"
