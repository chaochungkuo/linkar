#!/usr/bin/env bash
set -euo pipefail

mkdir -p "${LINKAR_RESULTS_DIR}/reports"

printf '<html><body>%s summary</body></html>\n' "${SAMPLE_NAME}" > "${LINKAR_RESULTS_DIR}/reports/${SAMPLE_NAME}_summary.html"
printf '<html><body>%s qc</body></html>\n' "${SAMPLE_NAME}" > "${LINKAR_RESULTS_DIR}/reports/${SAMPLE_NAME}_qc.html"
