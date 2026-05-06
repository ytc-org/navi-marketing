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
# Looks for ./credentials.json at the repo root (the GSC service account JSON,
# distributed to the team via 1Password). Skips silently if the file isn't
# there or if the `claude` CLI isn't on PATH.

ensure_gsc_mcp() {
    # The credentials file is a fixed convention: ./credentials.json at repo root.
    # cd into repo root happens at the top of this script, so $(pwd) is reliable.
    local gsc_path="$(pwd)/credentials.json"

    if [ ! -f "$gsc_path" ]; then
        # No credentials file — user hasn't set up GSC yet. Quiet hint, then move on.
        echo -e "  ${DIM}No credentials.json at repo root — GSC features disabled.${NC}"
        echo -e "  ${DIM}    Drop your service account JSON at ./credentials.json to enable.${NC}"
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

    # Always (re-)register so the MCP picks up the current credentials.json path.
    # If a stale registration exists pointing at an old path, this fixes it.
    # Both commands are idempotent: remove silently no-ops when nothing's registered.
    if claude mcp list 2>/dev/null | grep -qE "^gsc[: ]"; then
        # Already registered — assume it's fine. (claude mcp list doesn't expose env vars
        # so we can't verify the path matches; users with a stale registration can fix
        # it with `claude mcp remove gsc` and re-running this script.)
        return 0
    fi

    echo -e "  ${YELLOW}Registering the Google Search Console MCP with Claude Code...${NC}"
    if claude mcp add gsc \
        --scope user \
        -e GSC_CREDENTIALS_PATH="$gsc_path" \
        -e GSC_SKIP_OAUTH=true \
        -- "$uvx_path" mcp-search-console > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} GSC MCP registered (credentials: ./credentials.json)"
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
