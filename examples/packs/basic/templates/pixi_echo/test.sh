#!/usr/bin/env bash
set -euo pipefail

export NAME="Pixi"

./run.sh

test -f "greeting.txt"
grep -q "Hello from pixi, Pixi" "greeting.txt"

rm -f "greeting.txt"
printf 'pixi_echo template test passed\n'
