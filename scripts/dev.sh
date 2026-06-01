#!/bin/bash
# Chay dev mode cho tat ca tools backend

# Windows/Git Bash compatibility for venv activation
if [ -f "$(dirname "$0")/../.venv/Scripts/activate" ]; then
    source "$(dirname "$0")/../.venv/Scripts/activate"
elif [ -f "$(dirname "$0")/../.venv/bin/activate" ]; then
    source "$(dirname "$0")/../.venv/bin/activate"
fi

python "$(dirname "$0")/dev.py"
