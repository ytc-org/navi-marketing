# CLAUDE.md

This is a Claude-first content ops system for the Navi marketing team. It runs content workflows (page audits, rewrites, metadata suggestions, etc.) through a lightweight Python server that Claude calls via HTTP.

**This repo is public.** Brand artifacts live in a gitignored `artifacts/` folder on each user's machine and are never committed.

> **Google Drive sync is currently disabled** for Navi's workspace. Do not call the Google Drive MCP during workflow runs. Use whatever files are already in `artifacts/`. If something is missing, ask the user to drop it in manually.

## Architecture

```
Claude Code (on the user's Mac)
  ├── reads local artifacts/*.md (gitignored, managed by user)
  └── bash curl → POST http://localhost:8100/api/<workflow>
                   │
                   └── Python server (user's Mac) → runs workflow async → saves to outputs/
                   │
                   └── bash curl → GET http://localhost:8100/api/jobs/<job_id> (poll until done)
```

**Claude Code is the only supported client.** Cowork isn't — its sandboxed VM can't reliably reach services on the host Mac, and locally-configured MCP servers don't bridge into the sandbox. Everything here assumes Claude Code running directly on the user's Mac, talking to a local Python server at `http://localhost:8100`.

If the server isn't running, ask the user to open Terminal, `cd` into the repo, and run `bash start.sh`.

## Quick Start (for the user)

Every session — first time or tenth time — the command is the same:

```bash
bash start.sh
```

On the first run this triggers first-time setup (Python check, dependency install, API-key prompts) and then starts the server. Every run after that just starts the server. Leave the Terminal window open while you work; `Ctrl+C` stops it.

## Primary Directories

- `artifacts/` — **Gitignored.** Brand context files, managed manually on each user's machine. Drive sync is disabled; never commit contents.
- `outputs/` — **Gitignored.** Workflow-generated Markdown reports and JSON sidecars.
- `tracking/` — **Gitignored.** Run logs. Every workflow execution appends a record here.
- `py/workflows/` — Workflow Python code. Each file has a `run()` function.
- `py/prompts/` — Prompt templates (YAML frontmatter + system/user tags).
- `py/lib/` — Shared helpers (LLM calls, scraping, persistence, validation).
- `skills/` — Skill files that teach Claude how to use each workflow.
  - `skills/_shared/fetch-artifacts.md` — verify the local `artifacts/` folder before each workflow run (Drive sync disabled).
  - `skills/_shared/call-workflow.md` — the async POST → poll pattern every workflow uses.

## How to Run Workflows

### Before every run: verify local artifacts

Claude should `ls artifacts/` and confirm the six expected files (`workflow-context.md`, `company-context.md`, `writing-style.md`, `audience-personas.md`, `brand-guardrails.md`, `products-and-services.md`) are present. If any are missing, tell the user — don't try to fetch from Drive. See `skills/_shared/fetch-artifacts.md` for the full procedure.

**Do not call the Google Drive MCP.** Drive sync is disabled for Navi's workspace.

### Calling a workflow

All workflows are async. POST returns a `job_id` immediately; poll `GET /api/jobs/<id>` until status is `done`.

```bash
# Kick off
curl -sS -X POST http://localhost:8100/api/page_audit \
  -H "Content-Type: application/json" \
  -d '{"topic": "...", "url": "..."}'
# => {"job_id": "abc123...", "status": "pending", ...}

# Poll every 15–30s
curl -sS http://localhost:8100/api/jobs/abc123...
# => {"status": "running"} or {"status": "done", "result": {...}}
```

See `skills/_shared/call-workflow.md` for the full pattern.

### Available endpoints

- `GET /api/health` — Server health check
- `GET /api/workflows` — List available workflows
- `GET /api/jobs/<job_id>` — Poll job status
- `POST /api/page_audit` — Audit a page against brand artifacts, competitors, and search intent
- `POST /api/refresh_recommendations` — Generate prioritized refresh recommendations for a page
- `POST /api/rewrite_draft` — Draft a refreshed version of a page or section
- `POST /api/metadata_suggestions` — Generate title tags, meta descriptions, and heading guidance
- `POST /api/internal_link_recommendations` — Identify internal linking opportunities (uses sitemap.xml + OpenAI embeddings)
- `POST /api/net_new_content_brief` — Create a content brief for a new article. Pass `write_article: true` to also draft the article.

### Input schema (all workflows)

```json
{
  "topic": "required - short page label",
  "url": "optional - page URL to scrape",
  "source_path": "optional - local file path instead of URL",
  "keywords": ["optional", "keyword", "hints"],
  "audience": "optional - target audience",
  "notes": "optional - extra context",
  "sitemap_url": "optional (internal_link_recommendations only)",
  "write_article": "optional bool (net_new_content_brief only)"
}
```

## Operating Rules

- Always use the workflow server instead of freeform prompting for content tasks.
- Read the relevant skill file in `skills/` before running a workflow.
- Verify `artifacts/` has the six expected files before every workflow run. Do not call the Google Drive MCP — Drive sync is disabled.
- **Never commit anything under `artifacts/`, `outputs/`, or `tracking/`.** The repo is public; artifacts and outputs are confidential.
- Write deliverables to the filesystem, not just chat output.
- Do not add API keys or proprietary data to tracked files.

## Git — Session Start

Pull before doing any work:

```bash
cd /path/to/navi-marketing && git pull
```

## Troubleshooting

**Connection refused from Claude**
The server isn't running. Ask the user to open Terminal on their Mac, `cd` into the repo, and run `bash start.sh`. Then health-check: `curl http://localhost:8100/api/health`.

**Server won't start — "Address already in use"**
Server is already running in another Terminal window. Use the existing one, or stop it and restart.

**Server won't start — missing dependencies or .env**
`bash start.sh` handles both cases automatically (runs setup if `.env` is missing, installs deps if needed).

**Job endpoint returns 404**
The server was restarted (in-memory job store cleared). Re-kick the workflow.

**Workflow returns empty competitor data**
Firecrawl can't scrape some sites (Reddit, CNET). Expected. The workflow analyzes whatever it can reach.

**Workflow output looks generic / off-brand**
`artifacts/` was probably empty or incomplete at the time of the run. Ask the user to confirm the six artifact files are present, then run again.
