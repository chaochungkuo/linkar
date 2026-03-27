#!/usr/bin/env bash
set -euo pipefail

test_dir="${LINKAR_TEST_DIR:-./.tmp-test}"

export NAME="Linkar"
export LINKAR_RESULTS_DIR="${LINKAR_RESULTS_DIR:-${test_dir}/results}"

mkdir -p "${LINKAR_RESULTS_DIR}"

./run.sh

test -f "${LINKAR_RESULTS_DIR}/greeting.txt"
grep -q "Hello, Linkar" "${LINKAR_RESULTS_DIR}/greeting.txt"
