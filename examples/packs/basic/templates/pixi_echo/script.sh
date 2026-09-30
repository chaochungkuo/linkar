#!/usr/bin/env bash
set -euo pipefail

export RATTLER_CACHE_DIR="${PWD}/.rattler-cache"
mkdir -p "${RATTLER_CACHE_DIR}"

pixi run python write_greeting.py "${NAME}" > "greeting.txt"
