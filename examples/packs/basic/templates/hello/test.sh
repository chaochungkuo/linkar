#!/usr/bin/env bash
set -euo pipefail

export NAME="Linkar"

./run.sh

test -f "greeting.txt"
grep -q "Hello, Linkar" "greeting.txt"

rm -f "greeting.txt"
printf 'hello template test passed\n'
