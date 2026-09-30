#!/usr/bin/env bash
set -euo pipefail

export NAME="Pixi"

./script.sh

test -f "greeting.txt"
grep -q "Hello from pixi, Pixi" "greeting.txt"

rm -f "greeting.txt"
printf 'pixi_echo template test passed\n'
