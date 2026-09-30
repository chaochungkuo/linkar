#!/usr/bin/env bash
set -euo pipefail

unset PIXI_PROJECT_MANIFEST
export RATTLER_CACHE_DIR="${PWD}/.rattler-cache"
mkdir -p "${RATTLER_CACHE_DIR}"

pixi run pytest -q --junitxml pytest-report.xml
