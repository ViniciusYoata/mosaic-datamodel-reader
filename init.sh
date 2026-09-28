#!/usr/bin/env bash
#
# Automated Initialization Script for Mosaic Data Model Reader Skill
#
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
else
    echo "❌ Error: Python 3 was not found in your PATH." >&2
    echo "Please install Python 3.10 or higher to use this skill." >&2
    exit 1
fi

"$PYTHON_CMD" "$SCRIPT_DIR/scripts/init_env.py"
