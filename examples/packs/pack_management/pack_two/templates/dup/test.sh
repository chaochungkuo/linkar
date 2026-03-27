#!/usr/bin/env bash
set -euo pipefail

export NAME="two"
export LINKAR_RESULTS_DIR="./.tmp-test/results"

mkdir -p "${LINKAR_RESULTS_DIR}"

./run.sh

grep -q "pack two: two" "${LINKAR_RESULTS_DIR}/out.txt"
rm -rf "./.tmp-test"
printf 'pack_two dup template test passed\n'
