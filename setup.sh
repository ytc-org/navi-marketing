#!/bin/bash
# ──────────────────────────────────────────────────────────────────────────────
#
#   Content Ops Workflow Setup
#
#   This script gets everything ready to run on a brand-new machine.
#   It checks for Python, installs dependencies, and creates your .env file.
#
#   HOW TO RUN THIS:
#     1. Open Terminal (Mac: search "Terminal" in Spotlight / Launchpad)
#     2. Type: cd /path/to/this/folder    (drag the folder into Terminal to paste the path)
#     3. Type: bash setup.sh
#     4. Follow the prompts
#
# ──────────────────────────────────────────────────────────────────────────────

set -e

# ── Colors ────────────────────────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m' # No Color

# ── Helpers ───────────────────────────────────────────────────────────────────

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; }
info() { echo -e "  ${DIM}$1${NC}"; }

# ── Banner ────────────────────────────────────────────────────────────────────

clear
echo ""
echo -e "${CYAN}"
cat << 'BANNER'

     ██████╗ ██████╗ ███╗   ██╗████████╗███████╗███╗   ██╗████████╗
    ██╔════╝██╔═══██╗████╗  ██║╚══██╔══╝██╔════╝████╗  ██║╚══██╔══╝
    ██║     ██║   ██║██╔██╗ ██║   ██║   █████╗  ██╔██╗ ██║   ██║
    ██║     ██║   ██║██║╚██╗██║   ██║   ██╔══╝  ██║╚██╗██║   ██║
    ╚██████╗╚██████╔╝██║ ╚████║   ██║   ███████╗██║ ╚████║   ██║
     ╚═════╝ ╚═════╝ ╚═╝  ╚═══╝   ╚═╝   ╚══════╝╚═╝  ╚═══╝   ╚═╝

             ██████╗ ██████╗ ███████╗
            ██╔═══██╗██╔══██╗██╔════╝
            ██║   ██║██████╔╝███████╗
            ██║   ██║██╔═══╝ ╚════██║
            ╚██████╔╝██║     ███████║
             ╚═════╝ ╚═╝     ╚══════╝

BANNER
echo -e "${NC}"
echo -e "  ${BOLD}Content Ops Workflow Setup${NC}"
echo -e "  ${DIM}Let's get everything ready. This takes about 2 minutes.${NC}"
echo ""
echo -e "  ─────────────────────────────────────────────────"
echo ""

# ── Step 1: Check Python ─────────────────────────────────────────────────────

echo -e "  ${BOLD}Step 1/4: Checking Python${NC}"
echo ""

PYTHON_CMD=""

# Try python3 first (preferred), then python
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    # Make sure it's Python 3, not Python 2
    PY_VERSION=$(python --version 2>&1 | grep -oP '\d+' | head -1)
    if [ "$PY_VERSION" = "3" ]; then
        PYTHON_CMD="python"
    fi
fi

if [ -z "$PYTHON_CMD" ]; then
    fail "Python 3 is not installed."
    echo ""
    echo -e "  ${BOLD}How to install Python:${NC}"
    echo ""
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "    Option A (easiest): Download from https://python.org/downloads"
        echo "                        Click the big yellow button, run the installer."
        echo ""
        echo "    Option B (if you have Homebrew): brew install python3"
    elif [[ "$OSTYPE" == "linux"* ]]; then
        echo "    Run: sudo apt update && sudo apt install python3 python3-pip python3-venv"
    else
        echo "    Download from https://python.org/downloads"
        echo "    During install, CHECK THE BOX that says 'Add Python to PATH'"
    fi
    echo ""
    echo "  After installing, close this terminal, open a new one, and run this script again."
    exit 1
fi

PY_VERSION=$($PYTHON_CMD --version 2>&1)
PY_MAJOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.major)")
PY_MINOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.minor)")

if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]); then
    fail "Python 3.10+ is required. You have $PY_VERSION."
    echo ""
    echo "  Download the latest version from https://python.org/downloads"
    exit 1
fi

ok "Found $PY_VERSION (using '$PYTHON_CMD')"
echo ""

# ── Step 2: Install Python packages ──────────────────────────────────────────

echo -e "  ${BOLD}Step 2/4: Installing Python packages${NC}"
echo ""
info "This may take a minute..."
echo ""

if ! $PYTHON_CMD -m pip install -r py/requirements.txt --quiet 2>&1; then
    echo ""
    warn "pip install had issues. Trying with --user flag..."
    echo ""
    if ! $PYTHON_CMD -m pip install -r py/requirements.txt --user --quiet 2>&1; then
        echo ""
        fail "Could not install packages."
        echo ""
        echo "  Try running manually:"
        echo "    $PYTHON_CMD -m pip install -r py/requirements.txt"
        echo ""
        echo "  If that fails too, you may need to install pip:"
        if [[ "$OSTYPE" == "darwin"* ]]; then
            echo "    $PYTHON_CMD -m ensurepip --upgrade"
        else
            echo "    sudo apt install python3-pip"
        fi
        exit 1
    fi
fi

ok "All packages installed"
echo ""

# ── Step 3: Set up .env file ─────────────────────────────────────────────────

echo -e "  ${BOLD}Step 3/4: Setting up API keys${NC}"
echo ""

if [ -f ".env" ]; then
    # Check if it already has real keys
    if grep -q "^ANTHROPIC_API_KEY=sk-" .env 2>/dev/null; then
        ok ".env file exists with Anthropic key"
    else
        warn ".env file exists but Anthropic key may not be set"
        info "Open .env and make sure ANTHROPIC_API_KEY has your key"
    fi
    # Add GSC keys if missing (for users upgrading an older .env)
    if ! grep -q "^GSC_CREDENTIALS_PATH=" .env 2>/dev/null; then
        echo "" >> .env
        echo "# Google Search Console (service account auth)" >> .env
        echo "# Add the absolute path to your GSC service account JSON below." >> .env
        echo "GSC_CREDENTIALS_PATH=" >> .env
        echo "GSC_PROPERTY_URL=https://www.yournavi.com/" >> .env
        info "Added empty GSC_CREDENTIALS_PATH to .env — fill it in to enable GSC data in workflows."
    fi
    echo ""
else
    echo -e "  ${DIM}You'll need three API keys. Don't worry, I'll walk you through it.${NC}"
    echo ""

    # Anthropic key
    echo -e "  ${BOLD}Anthropic API Key${NC} (required — this powers the AI)"
    echo -e "  ${DIM}Get one at: https://console.anthropic.com/settings/keys${NC}"
    echo -e "  ${DIM}It starts with 'sk-ant-' and is about 100 characters long.${NC}"
    echo ""
    read -p "  Paste your Anthropic API key (or press Enter to skip for now): " ANTHROPIC_KEY
    echo ""

    # Firecrawl key
    echo -e "  ${BOLD}Firecrawl API Key${NC} (recommended — this powers web scraping)"
    echo -e "  ${DIM}Get one at: https://firecrawl.dev (free tier available)${NC}"
    echo -e "  ${DIM}It starts with 'fc-' and is about 32 characters long.${NC}"
    echo ""
    read -p "  Paste your Firecrawl API key (or press Enter to skip for now): " FIRECRAWL_KEY
    echo ""

    # OpenAI key
    echo -e "  ${BOLD}OpenAI API Key${NC} (required for internal-link recommendations — powers semantic similarity)"
    echo -e "  ${DIM}Get one at: https://platform.openai.com/api-keys${NC}"
    echo -e "  ${DIM}It starts with 'sk-' and is roughly 50+ characters long.${NC}"
    echo -e "  ${DIM}Used only by the internal_link_recommendations workflow. Skip if you don't plan to use it.${NC}"
    echo ""
    read -p "  Paste your OpenAI API key (or press Enter to skip for now): " OPENAI_KEY
    echo ""

    # GSC service account JSON path
    echo -e "  ${BOLD}Google Search Console Service Account${NC} (recommended — powers GSC data lookups in workflows)"
    echo -e "  ${DIM}Ask whoever set up Navi's GSC integration for the service account JSON file.${NC}"
    echo -e "  ${DIM}Save it somewhere safe on your Mac, then paste the absolute path here.${NC}"
    echo -e "  ${DIM}Example: /Users/yourname/Documents/navi-gsc-service-account.json${NC}"
    echo -e "  ${DIM}Skip if you don't have it yet — workflows will run without GSC data.${NC}"
    echo ""
    read -p "  Paste the absolute path to your GSC service account JSON (or press Enter to skip): " GSC_PATH
    echo ""

    # Validate the path if provided
    if [ -n "$GSC_PATH" ] && [ ! -f "$GSC_PATH" ]; then
        warn "File not found at: $GSC_PATH"
        info "Saving anyway — fix the path in .env later if needed."
        echo ""
    fi

    # Write .env
    cat > .env << EOF
# Content Ops Workflow API Keys
# ─────────────────────────────
# These are secret — don't share them or commit this file to git.

ANTHROPIC_API_KEY=${ANTHROPIC_KEY}
FIRECRAWL_API_KEY=${FIRECRAWL_KEY}
OPENAI_API_KEY=${OPENAI_KEY}

# Google Search Console (service account auth)
# Path to the service account JSON. The MCP server reads it via GSC_CREDENTIALS_PATH.
GSC_CREDENTIALS_PATH=${GSC_PATH}
GSC_PROPERTY_URL=https://www.yournavi.com/
EOF

    if [ -n "$ANTHROPIC_KEY" ]; then
        ok "Created .env with your API keys"
    else
        warn "Created .env but you still need to add your Anthropic key"
        info "Open the .env file and paste your key after ANTHROPIC_API_KEY="
    fi
    echo ""
fi

# ── Step 4: Verify everything works ──────────────────────────────────────────

echo -e "  ${BOLD}Step 4/4: Verifying setup${NC}"
echo ""

# Quick smoke test — import the server module
VERIFY_RESULT=$($PYTHON_CMD -c "
import sys
sys.path.insert(0, 'py')
try:
    from lib.validation import WorkflowInput
    from lib.artifacts import load_artifacts
    from lib.prompts import load_prompt
    from lib.llm import call_claude
    from lib.scrape import scrape_page
    from lib.persistence import persist_workflow_run
    from lib.sitemap import parse_sitemap
    from lib.embeddings import rank_urls_by_similarity
    print('OK')
except Exception as e:
    print(f'FAIL: {e}')
" 2>&1)

if [[ "$VERIFY_RESULT" == "OK" ]]; then
    ok "All modules load correctly"
else
    fail "Module import failed: $VERIFY_RESULT"
    echo ""
    echo "  This probably means a package didn't install correctly."
    echo "  Try: $PYTHON_CMD -m pip install -r py/requirements.txt"
    exit 1
fi

# Check artifacts — note: artifacts are expected to be empty initially.
# Claude populates artifacts/ from the shared Google Drive folder before each workflow run.
ARTIFACT_COUNT=$(ls artifacts/*.md 2>/dev/null | wc -l | tr -d ' ')
if [ "$ARTIFACT_COUNT" -gt 0 ]; then
    ok "Found $ARTIFACT_COUNT artifact files in artifacts/ (from a previous run)"
else
    info "artifacts/ is empty — this is normal. Claude will pull them from Google Drive before each workflow."
fi

echo ""

# ── Done ──────────────────────────────────────────────────────────────────────

echo -e "  ─────────────────────────────────────────────────"
echo ""
echo -e "  ${GREEN}${BOLD}Setup complete!${NC}"
echo ""
echo -e "  ${BOLD}Next time — and every time after — just run:${NC}"
echo ""
echo -e "    ${CYAN}bash start.sh${NC}"
echo ""
echo -e "  ${DIM}That one command starts the workflow server. Leave the${NC}"
echo -e "  ${DIM}Terminal window open while you work in Claude.${NC}"
echo ""
echo -e "  ─────────────────────────────────────────────────"
echo ""
echo ""
read -p "  Start the server now? [Y/n] " START_NOW
START_NOW=${START_NOW:-Y}
if [[ "$START_NOW" =~ ^[Yy] ]]; then
    echo ""
    exec bash start.sh
fi
echo ""
echo -e "  ${DIM}No worries — run ${NC}${CYAN}bash start.sh${NC}${DIM} whenever you're ready.${NC}"
echo ""
