#!/bin/bash
# Script de build toan bo du an
# Chay build.py trong virtual environment

if [ -f "$(dirname "$0")/../.venv/Scripts/python" ]; then
    "$(dirname "$0")/../.venv/Scripts/python" "$(dirname "$0")/build.py"
elif [ -f "$(dirname "$0")/../.venv/bin/python" ]; then
    "$(dirname "$0")/../.venv/bin/python" "$(dirname "$0")/build.py"
else
    python "$(dirname "$0")/build.py"
fi
