#!/usr/bin/env bash
set -euo pipefail

export VALUE="demo"
tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/produce_data.XXXXXX")"
export LINKAR_RESULTS_DIR="${tmp_dir}/results"
trap 'rm -rf "${tmp_dir}"' EXIT

mkdir -p "${LINKAR_RESULTS_DIR}"
./run.sh
test -f "${LINKAR_RESULTS_DIR}/dataset/sample.txt"
printf 'produce_data template test passed\n'
