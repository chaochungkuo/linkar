#!/usr/bin/env bash
set -euo pipefail

unset PIXI_PROJECT_MANIFEST

pixi run pytest -q --junitxml pytest-report.xml
