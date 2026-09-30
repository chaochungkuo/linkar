#!/usr/bin/env bash
set -euo pipefail

message="$(cat "${RESULTS_DIR}/message.txt")"
printf 'consumed: %s\n' "${message}" > "${LINKAR_RESULTS_DIR}/consumed.txt"
