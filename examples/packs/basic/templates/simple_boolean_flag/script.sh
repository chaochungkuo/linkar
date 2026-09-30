#!/usr/bin/env bash
set -euo pipefail

punctuation="."
if [[ "${EXCITED}" == "true" ]]; then
  punctuation="!"
fi

printf 'Hello, %s%s\n' "${NAME}" "${punctuation}" > "${LINKAR_RESULTS_DIR}/greeting.txt"
