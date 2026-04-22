# CLAUDE.md

This is a Claude-first content ops system for the Navi marketing team. It runs content workflows (page audits, rewrites, metadata suggestions, etc.) through a lightweight Python server that Claude calls via HTTP.

**This repo is public.** Brand artifacts live in Google Drive, are fetched by Claude into a gitignored `artifacts/` folder before each workflow run, and are never committed.

## Architecture

```
Claude (Cowork)
  ├── Drive MCP → fetches artifacts → writes artifacts/*.md (gitignored)
  └── bash curl → POST http://localhost:8100/api/<workflow>
                   │
                   └── Python server → runs workflow async → saves to outputs/
                   │
                   └── bash curl → GET /api/jobs/<job_id> (poll until done)
```

Server runs inside Cowork's bash sandbox (Claude starts it via `nohup python3 py/server.py &`). Reachable at `http://localhost:8100` from subsequent bash calls. Outputs land in the sandbox; Claude copies each deliverable to the session outputs dir and shares it as a `computer://` link so the user can save it.

If the user chooses to start the server themselves on their Mac, it's reachable at `http://host.docker.internal:8100` instead — workflows still work the same way.

## Quick Start

### First-time setup (once)

```bash
bash setup.sh
```

Checks Python, installs dependencies, prompts for API keys.

### Starting the server

Claude starts it automatically inside the bash sandbox before the first workflow each session. If you want to run it on your Mac instead (so outputs land in your local `outputs/` folder), do:

```bash
python3 py/server.py
```

Leave the Terminal window open while using workflows. Server runs on port 8100.

### Stopping the server

If Claude started it: it runs until the sandbox is torn down. No action needed.
If you started it: `Ctrl+C` in the Terminal window.

## Primary Directories

- `artifacts/` — **Gitignored.** Brand context files, populated at runtime from Drive folder [1LLmvyrvzc3JTS_FSqlcmxQcSTPaJ_C0f](https://drive.google.com/drive/folders/1LLmvyrvzc3JTS_FSqlcmxQcSTPaJ_C0f). Never commit contents.
- `outputs/` — **Gitignored.** Workflow-generated Markdown reports and JSON sidecars.
- `tracking/` — **Gitignored.** Run logs. Every workflow execution appends a record here.
- `py/workflows/` — Workflow Python code. Each file has a `run()` function.
- `py/prompts/` — Prompt templates (YAML frontmatter + system/user tags).
- `py/lib/` — Shared helpers (LLM calls, scraping, persistence, validation).
- `skills/` — Skill files that teach Claude how to use each workflow.
  - `skills/_shared/fetch-artifacts.md` — the Drive-fetch prerequisite every workflow needs.
  - `skills/_shared/call-workflow.md` — the async POST → poll pattern every workflow uses.

## How to Run Workflows

### Before every run: fetch artifacts from Drive

Claude should call the Google Drive MCP to pull the six expected docs (`workflow-context`, `company-context`, `writing-style`, `audience-personas`, `brand-guardrails`, `products-and-services`) from the Drive folder and write them to `artifacts/` as Markdown. See `skills/_shared/fetch-artifacts.md` for the full procedure.

If artifacts were fetched earlier in the same conversation and Drive hasn't been edited since, skipping the re-fetch is fine.

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
- Fetch artifacts from Drive before every workflow run (or confirm you already did it this conversation).
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
The server isn't running. Claude should start it in the bash sandbox (`nohup python3 py/server.py > /tmp/wf-server.log 2>&1 &`) and health-check with `curl http://localhost:8100/api/health`.

**Server won't start — "Address already in use"**
Server is already running. Use the existing one, or kill it and restart.

**Server won't start — missing dependencies**
Run: `python3 -m pip install -r py/requirements.txt`

**Server won't start — missing .env**
Run: `bash setup.sh` to create and configure your .env file.

**Job endpoint returns 404**
The server was restarted (in-memory job store cleared). Re-kick the workflow.

**Workflow returns empty competitor data**
Firecrawl can't scrape some sites (Reddit, CNET). Expected. The workflow analyzes whatever it can reach.

**Workflow output looks generic / off-brand**
`artifacts/` was probably empty at the time of the run. Re-fetch from Drive and run again.
