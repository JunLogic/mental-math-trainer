#!/bin/bash
set -e

cd "$(dirname "$0")"

# Find Python 3.10+
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        version=$("$cmd" -c "import sys; print(sys.version_info >= (3, 10))" 2>/dev/null)
        if [ "$version" = "True" ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "Error: Python 3.10 or newer is required."
    echo "Install it from https://www.python.org/downloads/"
    exit 1
fi

# Create virtual environment if needed
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    "$PYTHON" -m venv .venv
fi

source .venv/bin/activate

# Install dependencies only when needed
MARKER=".venv/.deps_installed"
if [ ! -f "$MARKER" ] || [ "requirements.txt" -nt "$MARKER" ]; then
    echo "Installing dependencies..."
    pip install -q -r requirements.txt
    touch "$MARKER"
fi

echo ""
echo "=============================="
echo "  Mental Math Trainer"
echo "=============================="
echo ""

python -m app.cli "$@"
