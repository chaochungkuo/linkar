#!/usr/bin/env bash
set -euo pipefail

pixi run python write_greeting.py "${NAME}" > "greeting.txt"
