#!/bin/bash
# ──────────────────────────────────────────────────────────────────────────────
#
#   Content Ops Workflow — One-Command Launcher
#
#   Run this once per work session. It will:
#     1. Check your setup (Python, dependencies, API keys)
#     2. Run first-time setup if needed
#     3. Start the workflow server
#
#   HOW TO RUN:
#     1. Open Terminal
#     2. cd into this folder
#     3. Run:  bash start.sh
#
#   Then leave the Terminal window open and talk to Claude in Cowork
#   (or Claude Code) like normal.
#
# ──────────────────────────────────────────────────────────────────────────────

set -e

# ── Colors ────────────────────────────────────────────────────────────────────

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

# ── Move to repo root (so paths work regardless of where the user ran from) ──

cd "$(dirname "$0")"

# ── Pick a Python interpreter ────────────────────────────────────────────────

PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PY_MAJOR=$(python -c "import sys; print(sys.version_info.major)" 2>/dev/null || echo "0")
    if [ "$PY_MAJOR" = "3" ]; then
        PYTHON_CMD="python"
    fi
fi

if [ -z "$PYTHON_CMD" ]; then
    echo ""
    echo -e "  ${YELLOW}Python 3 isn't installed on this Mac.${NC}"
    echo ""
    echo "  Install it from https://python.org/downloads and run this script again."
    echo ""
    exit 1
fi

# ── If .env is missing, run first-time setup ─────────────────────────────────

if [ ! -f ".env" ]; then
    echo ""
    echo -e "  ${BOLD}First run detected — kicking off setup.${NC}"
    echo -e "  ${DIM}(You only have to do this once.)${NC}"
    echo ""
    sleep 1
    bash setup.sh
    echo ""
    echo -e "  ${DIM}Setup finished. Starting the server now...${NC}"
    echo ""
    sleep 1
fi

# ── Make sure dependencies are installed (cheap no-op if they already are) ──

if ! $PYTHON_CMD -c "import anthropic, dotenv, yaml, pydantic, firecrawl" 2>/dev/null; then
    echo ""
    echo -e "  ${YELLOW}Missing dependencies — installing now...${NC}"
    echo ""
    $PYTHON_CMD -m pip install -r py/requirements.txt --quiet
    echo -e "  ${GREEN}Done.${NC}"
    echo ""
fi

# ── Launch the server (exec so Ctrl+C goes straight to Python) ───────────────

exec $PYTHON_CMD py/server.py "$@"
