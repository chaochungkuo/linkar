#!/usr/bin/env bash
set -euo pipefail

export SOURCE_URL="file://$(pwd)/testdata/source.txt"
export OUTPUT_NAME="fetched.txt"
export LINKAR_RESULTS_DIR="./.tmp-test/results"

mkdir -p "${LINKAR_RESULTS_DIR}"

./run.sh

test -f "${LINKAR_RESULTS_DIR}/fetched.txt"
grep -q "downloaded through Linkar" "${LINKAR_RESULTS_DIR}/fetched.txt"

rm -rf "./.tmp-test"
printf 'download_test_data template test passed\n'
