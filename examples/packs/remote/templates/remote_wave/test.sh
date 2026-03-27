#!/usr/bin/env bash
set -euo pipefail

export NAME="remote"
export LINKAR_RESULTS_DIR="./.tmp-test/results"

mkdir -p "${LINKAR_RESULTS_DIR}"

./run.sh

grep -q "remote wave, remote" "${LINKAR_RESULTS_DIR}/wave.txt"
rm -rf "./.tmp-test"
printf 'remote_wave template test passed\n'
