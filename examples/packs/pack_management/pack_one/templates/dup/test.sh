#!/usr/bin/env bash
set -euo pipefail

export NAME="one"
export LINKAR_RESULTS_DIR="./.tmp-test/results"

mkdir -p "${LINKAR_RESULTS_DIR}"

./run.sh

grep -q "pack one: one" "${LINKAR_RESULTS_DIR}/out.txt"
rm -rf "./.tmp-test"
printf 'pack_one dup template test passed\n'
