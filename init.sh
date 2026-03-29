#!/bin/bash
# init.sh - Turtle Investment Framework environment setup (uv)
# Run at the start of each session

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

echo "=== Turtle Investment Framework - Environment Setup ==="
echo "Project root: $PROJECT_ROOT"
echo ""

# 1. Python environment (uv + venv)
VENV_DIR="$PROJECT_ROOT/.venv"
PYTHON_BIN="$VENV_DIR/bin/python"

echo "[1/5] Setting up Python environment..."

if ! command -v uv >/dev/null 2>&1; then
    echo "  ERROR: uv is not installed"
    echo "  Install uv: brew install uv"
    exit 1
fi

if [ ! -f "$PYTHON_BIN" ]; then
    echo "  Creating venv at $VENV_DIR with uv (Python >= 3.10) ..."
    uv venv "$VENV_DIR" --python 3.10
    VENV_JUST_CREATED=1
else
    VENV_JUST_CREATED=0
fi

PY_VER=$($PYTHON_BIN -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')

export PATH="$VENV_DIR/bin:$PATH"
echo "  uv: $(uv --version)"
echo "  Python: $($PYTHON_BIN --version)"
echo "  Using: $PYTHON_BIN"

# 2. Install dependencies (on first create or --force-install)
echo "[2/5] Installing Python dependencies..."
if [ "$VENV_JUST_CREATED" -eq 1 ] || [ "$1" = "--force-install" ]; then
    uv pip sync --python "$PYTHON_BIN" requirements.txt
    echo "  Dependencies installed."
else
    echo "  Skipped (venv exists). Use 'bash init.sh --force-install' to reinstall."
fi

# 3. Verify Tushare token
echo "[3/5] Checking Tushare token..."
# Source .env file if present
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
    echo "  Loaded .env file"
fi
if [ -z "$TUSHARE_TOKEN" ]; then
    echo "  WARNING: TUSHARE_TOKEN not set"
    echo "  Option 1: cp .env.sample .env && edit .env"
    echo "  Option 2: export TUSHARE_TOKEN='your_token_here'"
    echo "  Tests requiring live API will be skipped"
else
    echo "  TUSHARE_TOKEN: set (${#TUSHARE_TOKEN} chars)"
fi

# 4. Create output directory
echo "[4/5] Ensuring output directory..."
mkdir -p output

# 5. Run basic tests
echo "[5/5] Running verification tests..."
$PYTHON_BIN -m pytest tests/ -x -q --tb=short

echo ""
echo "=== Setup complete ==="
echo "To run: uv run python scripts/tushare_collector.py --code 600887.SH --output output/data_pack_market.md"
