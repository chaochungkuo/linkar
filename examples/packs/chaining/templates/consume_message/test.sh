#!/usr/bin/env bash
set -euo pipefail

export RESULTS_DIR="./testdata/producer-results"
export LINKAR_RESULTS_DIR="./.tmp-test/results"

mkdir -p "${LINKAR_RESULTS_DIR}"

./run.sh

test -f "${LINKAR_RESULTS_DIR}/consumed.txt"
grep -q "consumed: hello from producer" "${LINKAR_RESULTS_DIR}/consumed.txt"

rm -rf "./.tmp-test"
printf 'consume_message template test passed\n'
