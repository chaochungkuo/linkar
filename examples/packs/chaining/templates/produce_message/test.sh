#!/usr/bin/env bash
set -euo pipefail

export MESSAGE="hello from chaining"
export LINKAR_RESULTS_DIR="./.tmp-test/results"

mkdir -p "${LINKAR_RESULTS_DIR}"

./run.sh

test -f "${LINKAR_RESULTS_DIR}/message.txt"
grep -q "hello from chaining" "${LINKAR_RESULTS_DIR}/message.txt"

rm -rf "./.tmp-test"
printf 'produce_message template test passed\n'
