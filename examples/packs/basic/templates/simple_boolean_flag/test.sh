#!/usr/bin/env bash
set -euo pipefail

export NAME="Boolean"
export EXCITED="true"
export LINKAR_RESULTS_DIR="./.tmp-test/results"

mkdir -p "${LINKAR_RESULTS_DIR}"

./run.sh

test -f "${LINKAR_RESULTS_DIR}/greeting.txt"
grep -q "Hello, Boolean!" "${LINKAR_RESULTS_DIR}/greeting.txt"

rm -rf "./.tmp-test"
printf 'simple_boolean_flag template test passed\n'
