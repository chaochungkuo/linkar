#!/usr/bin/env bash
set -euo pipefail

export SAMPLE_NAME="demo"
export LINKAR_RESULTS_DIR="./.tmp-test/results"

mkdir -p "${LINKAR_RESULTS_DIR}"

./run.sh

test -f "${LINKAR_RESULTS_DIR}/reports/demo_summary.html"
test -f "${LINKAR_RESULTS_DIR}/reports/demo_qc.html"

rm -rf "./.tmp-test"
printf 'glob_reports template test passed\n'
