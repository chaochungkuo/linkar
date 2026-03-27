#!/usr/bin/env bash
set -euo pipefail

export NAME="Pytest"

./run.sh

test -f "pytest-report.xml"
grep -q 'tests="1"' "pytest-report.xml"
grep -q 'failures="0"' "pytest-report.xml"

rm -f "pytest-report.xml"
printf 'pixi_pytest template test passed\n'
