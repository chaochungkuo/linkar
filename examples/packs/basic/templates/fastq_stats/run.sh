#!/usr/bin/env bash
set -euo pipefail

read_count="$(awk 'END { print NR / 4 }' "${INPUT_FASTQ}")"

{
  printf 'sample=%s\n' "${SAMPLE_NAME}"
  printf 'reads=%s\n' "${read_count}"
} > "${LINKAR_RESULTS_DIR}/summary.txt"
