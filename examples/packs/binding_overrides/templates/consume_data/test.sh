#!/usr/bin/env bash
set -euo pipefail

template_dir="$(cd "$(dirname "$0")" && pwd)"
export SOURCE_DIR="${template_dir}/../../fixtures/override_source"
tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/consume_data.XXXXXX")"
export LINKAR_RESULTS_DIR="${tmp_dir}/results"
trap 'rm -rf "${tmp_dir}"' EXIT

mkdir -p "${LINKAR_RESULTS_DIR}"
./run.sh
test -f "${LINKAR_RESULTS_DIR}/copied.txt"
grep -q '^override$' "${LINKAR_RESULTS_DIR}/copied.txt"
printf 'consume_data template test passed\n'
