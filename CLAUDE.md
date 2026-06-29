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
  - `skills/_shared/fetch-gsc.md` — the Google Search Console MCP fetch pattern (page metrics, top queries, trends) for workflows that benefit from real performance data.
  - `skills/_shared/call-workflow.md` — the async POST → poll pattern every workflow uses.
  - `skills/gsc-reports/SKILL.md` — generate ranking reports and HTML dashboards directly from the GSC MCP (no Python server). Use for "where does everything rank," mobile vs. desktop, movers, opportunity finding.
- `templates/artifacts/` — copyable templates for the optional, hand-maintained artifacts (`plans-and-pricing`, `recommendation-guardrails`). Copy into `artifacts/` and fill in.

## How to Run Workflows

### Before every run: verify local artifacts

Claude should `ls artifacts/` and confirm the six expected files (`workflow-context.md`, `company-context.md`, `writing-style.md`, `audience-personas.md`, `brand-guardrails.md`, `products-and-services.md`) are present. If any are missing, tell the user — don't try to fetch from Drive. See `skills/_shared/fetch-artifacts.md` for the full procedure.

Two **optional** artifacts are used automatically when present (don't block a run if absent): `plans-and-pricing.md` (current plan/price data so workflows stop citing stale plans) and `recommendation-guardrails.md` (the team's "stop telling me that" suppression list). Templates live in `templates/artifacts/`.

**Do not call the Google Drive MCP.** Drive sync is disabled for Navi's workspace.

### The feedback loop (improving recommendation quality over time)

When a workflow keeps surfacing a kind of recommendation that isn't useful (or is a false positive), don't just ignore it run after run — record it so future runs honor it. Append a one-line rule to `artifacts/recommendation-guardrails.md` (create it from the template if needed). The page-audit and refresh workflows inject that file into their evaluation/synthesis steps and are instructed to suppress matching findings. If the user says something like "the audit keeps flagging X and it's not helpful," offer to add the guardrail for them.

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
  "gsc": "optional - structured Google Search Console data (see py/lib/gsc.py)",
  "sitemap_url": "optional (internal_link_recommendations only)",
  "write_article": "optional bool (net_new_content_brief only)"
}
```

The `gsc` field is a structured object with fields like `property_url`, `date_range`, `page_totals`, `comparison`, `top_queries`, `top_pages`, and `notes`. Skills are responsible for fetching the right slice from the GSC MCP and populating it. See `skills/_shared/fetch-gsc.md` for the per-workflow guidance and `py/lib/gsc.py` for the exact shape. When omitted, workflows run unchanged — GSC is purely additive.

## Operating Rules

- Always use the workflow server instead of freeform prompting for content tasks.
- Read the relevant skill file in `skills/` before running a workflow.
- Verify `artifacts/` has the six expected files before every workflow run. Do not call the Google Drive MCP — Drive sync is disabled.
- For workflows whose `SKILL.md` lists GSC as a prerequisite, query the GSC MCP first and populate the workflow's `gsc` input field. See `skills/_shared/fetch-gsc.md`.
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

**GSC tools aren't visible in Claude Code**
`start.sh` registers the `gsc` MCP server with `claude mcp add` on first run, but only if `./credentials.json` (the GSC service-account JSON, distributed via 1Password) exists at the repo root. If the tools don't appear: (1) confirm `./credentials.json` exists in the repo, (2) confirm `bash start.sh` has been run this session, (3) restart Claude Code so it picks up the registration, (4) run `claude mcp list` to confirm `gsc` is registered. If it's registered with a stale path (e.g. pointing at an old location from a previous setup), run `claude mcp remove gsc` and re-run `bash start.sh` to re-register against `./credentials.json`.

**GSC returns no data for a URL**
The service account email must have access to the Navi GSC property. Verify in Search Console → Settings → Users and permissions. Also confirm you queried the right property URL — Navi's is `https://www.yournavi.com/` (URL-prefix, **with** the `www.`). Calls to `https://yournavi.com/` will return empty data.

**Server logs show `[throttle] slept Xs ...` between calls**
Expected. The LLM client in `py/lib/llm.py` enforces a per-model sliding-window rate-limit budget (`py/lib/token_budget.py`) so workflows don't trip Anthropic 429s. Anthropic limits each model class (Opus / Sonnet / Haiku) **independently**, and input (ITPM) and output (OTPM) tokens are **separate buckets** — there is no combined cap. Defaults are Anthropic's Tier 1 limits: Opus 500k ITPM / 80k OTPM, Sonnet 30k / 8k, Haiku 50k / 10k (all 50 RPM). When a call wouldn't fit a model's remaining window it sleeps until budget frees up; a workflow may take several minutes wall-clock. Sonnet is the tightest model and the usual reason for a wait. If the org's account is above Tier 1, set `ANTHROPIC_RATE_LIMIT_TIER` (`1`–`4`) in `.env`. The per-call `[tokens] <class> in=… out=… (window …)` line shows actual usage and remaining budget for that model.

**Workflow fails immediately with `TokenBudgetExceededError`**
A single call's estimated input exceeds that model's effective ITPM, or its `max_tokens` (× output ratio) exceeds the model's effective OTPM — throttling can't help because even one call doesn't fit. The error names the model class and offending size. Fixes: reduce input (smaller artifacts, fewer/shorter competitor scrapes, shorter source page), lower the prompt's `maxTokens`, move the call to a model with a higher limit (Opus has by far the most headroom), or raise `ANTHROPIC_RATE_LIMIT_TIER` if the account is genuinely above Tier 1.
