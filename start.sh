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

# ── Ensure GSC MCP is installed and registered with Claude Code ──────────────
# Skips silently if the user hasn't filled in GSC_CREDENTIALS_PATH or doesn't
# have the `claude` CLI on their PATH.

ensure_gsc_mcp() {
    # Read GSC creds path from .env without exporting everything
    local gsc_path
    gsc_path=$(grep -E "^GSC_CREDENTIALS_PATH=" .env 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'")

    if [ -z "$gsc_path" ]; then
        return 0  # User opted out of GSC
    fi

    if [ ! -f "$gsc_path" ]; then
        echo -e "  ${YELLOW}⚠  GSC_CREDENTIALS_PATH points to a missing file: $gsc_path${NC}"
        echo -e "  ${DIM}    Fix it in .env to enable GSC data in workflows. Skipping MCP setup.${NC}"
        echo ""
        return 0
    fi

    if ! command -v claude &> /dev/null; then
        echo -e "  ${DIM}claude CLI not found on PATH — skipping GSC MCP setup.${NC}"
        return 0
    fi

    # Install uv (which provides uvx) if missing — needed to run the GSC MCP
    if ! command -v uvx &> /dev/null; then
        echo -e "  ${YELLOW}Installing uv (needed for the GSC MCP server)...${NC}"
        curl -LsSf https://astral.sh/uv/install.sh | sh > /dev/null 2>&1
        # uv installs to ~/.local/bin by default — make it visible for the rest of this script
        export PATH="$HOME/.local/bin:$PATH"
        if ! command -v uvx &> /dev/null; then
            echo -e "  ${YELLOW}⚠  uv install didn't succeed. Skipping GSC MCP setup.${NC}"
            echo -e "  ${DIM}    Install manually: curl -LsSf https://astral.sh/uv/install.sh | sh${NC}"
            echo ""
            return 0
        fi
        echo -e "  ${GREEN}✓${NC} uv installed"
    fi

    # Resolve the absolute path to uvx — Claude Code's MCP spawn doesn't always
    # see the user's shell PATH, so passing the full path avoids "spawn uvx ENOENT"
    local uvx_path
    uvx_path=$(command -v uvx)

    # If GSC MCP is already registered, we're done
    if claude mcp list 2>/dev/null | grep -qE "^gsc[: ]"; then
        return 0
    fi

    echo -e "  ${YELLOW}Registering the Google Search Console MCP with Claude Code...${NC}"
    if claude mcp add gsc \
        --scope user \
        -e GSC_CREDENTIALS_PATH="$gsc_path" \
        -e GSC_SKIP_OAUTH=true \
        -- "$uvx_path" mcp-search-console > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} GSC MCP registered"
        echo -e "  ${DIM}    Restart Claude Code if you don't see the gsc:* tools yet.${NC}"
        echo ""
    else
        echo -e "  ${YELLOW}⚠  Couldn't register the GSC MCP automatically.${NC}"
        echo -e "  ${DIM}    Run this manually:${NC}"
        echo -e "  ${DIM}    claude mcp add gsc --scope user -e GSC_CREDENTIALS_PATH=\"$gsc_path\" -e GSC_SKIP_OAUTH=true -- $uvx_path mcp-search-console${NC}"
        echo ""
    fi
}

ensure_gsc_mcp

# ── Launch the server (exec so Ctrl+C goes straight to Python) ───────────────

exec $PYTHON_CMD py/server.py "$@"
