#!/bin/bash
# Launcher script for Dictator voice assistant.
# This script activates the venv and runs the main entry point.
# Paths are resolved relative to the script's location.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "Error: Virtual environment not found at $VENV_DIR"
    echo "Run 'make install' or './install.sh' first."
    exit 1
fi

source "$VENV_DIR/bin/activate"
cd "$SCRIPT_DIR"

exec python -u dictate.py "$@"
