#!/usr/bin/env bash
# Build portable distributable for current OS (Linux/macOS).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR=".venv-build"

# Pick a Python with Tk support (customtkinter needs tkinter).
find_python_with_tk() {
    local candidates=()
    if [[ -n "${PYTHON:-}" ]]; then
        candidates+=("$PYTHON")
    fi
    if command -v brew >/dev/null 2>&1; then
        candidates+=("$(brew --prefix)/bin/python3")
    fi
    candidates+=("python3" "python")
    for c in "${candidates[@]}"; do
        if command -v "$c" >/dev/null 2>&1; then
            if "$c" -c "import tkinter; assert tkinter.TkVersion >= 8.6" >/dev/null 2>&1; then
                echo "$c"
                return 0
            fi
        fi
    done
    return 1
}

if ! PYTHON_BIN="$(find_python_with_tk)"; then
    echo "ERROR: no Python with Tk >= 8.6 found." >&2
    echo "  macOS:   brew install python-tk@3.14" >&2
    echo "  Linux:   sudo apt install python3-tk" >&2
    echo "  Or set PYTHON=/path/to/python with Tk available" >&2
    exit 1
fi

echo ">> Using Python: $PYTHON_BIN"

if [ ! -d "$VENV_DIR" ] || [ ! -x "$VENV_DIR/bin/python" ]; then
    echo ">> Creating virtualenv..."
    "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# Sanity-check: venv must have Tk (customtkinter needs it).
if ! "$VENV_DIR/bin/python" -c "import tkinter; assert tkinter.TkVersion >= 8.6" >/dev/null 2>&1; then
    echo "ERROR: venv ($VENV_DIR) lacks Tk. Recreate it with a Python that has Tk support." >&2
    echo "  Remove $VENV_DIR and rerun, or set PYTHON=/path/to/python-with-tk" >&2
    exit 1
fi

echo ">> Installing dependencies..."
"$VENV_DIR/bin/python" -m pip install --upgrade pip --quiet
"$VENV_DIR/bin/python" -m pip install -r requirements.txt pyinstaller --quiet

echo ">> Building executable (single file, no console)..."
"$VENV_DIR/bin/pyinstaller" \
    --name "MCBuilder" \
    --onefile \
    --noconsole \
    --noconfirm \
    --clean \
    --add-data "mcbuilder/templates:mcbuilder/templates" \
    --add-data "mcbuilder/assets:mcbuilder/assets" \
    --collect-all customtkinter \
    --collect-all tkinter \
    --paths . \
    --hidden-import customtkinter \
    --hidden-import tkinter \
    --hidden-import tkinter.ttk \
    --hidden-import tkinter.filedialog \
    --hidden-import tkinter.messagebox \
    --hidden-import mcbuilder \
    run.py

echo ""
echo "✓ Done. Binary: dist/MCBuilder"
echo "  Run with: ./dist/MCBuilder"
