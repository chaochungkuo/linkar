#!/usr/bin/env bash
set -euo pipefail

export INPUT_FASTQ="./testdata/sample.fastq"
export SAMPLE_NAME="demo"
export LINKAR_RESULTS_DIR="./.tmp-test/results"

mkdir -p "${LINKAR_RESULTS_DIR}"

./run.sh

test -f "${LINKAR_RESULTS_DIR}/summary.txt"
grep -q "sample=demo" "${LINKAR_RESULTS_DIR}/summary.txt"
grep -q "reads=2" "${LINKAR_RESULTS_DIR}/summary.txt"

rm -rf "./.tmp-test"
printf 'fastq_stats template test passed\n'
