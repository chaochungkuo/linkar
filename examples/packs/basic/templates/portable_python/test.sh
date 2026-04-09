#!/usr/bin/env bash
set -euo pipefail

export NAME="Portable"
export LINKAR_RESULTS_DIR="./.tmp-test/results"

mkdir -p "${LINKAR_RESULTS_DIR}"

./run.sh

test -f "${LINKAR_RESULTS_DIR}/greeting.txt"
grep -q "Hello from Portable" "${LINKAR_RESULTS_DIR}/greeting.txt"

rm -rf "./.tmp-test"
printf 'portable_python template test passed\n'
