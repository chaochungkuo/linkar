#!/usr/bin/env bash
set -euo pipefail

export INPUT_FILE="./testdata/input.txt"
export LINKAR_RESULTS_DIR="./.tmp-test/results"

mkdir -p "${LINKAR_RESULTS_DIR}"

./run.sh

test -f "${LINKAR_RESULTS_DIR}/copied.txt"
grep -q "copied through Linkar" "${LINKAR_RESULTS_DIR}/copied.txt"

rm -rf "./.tmp-test"
printf 'simple_file_input template test passed\n'
