# How to Call a Workflow (shared pattern)

All workflows are async. The flow is:

1. Make sure the workflow server is running (start it if needed).
2. `POST /api/<workflow>` — returns a `job_id` immediately.
3. `GET /api/jobs/<job_id>` — poll every 15–30 seconds until `status` is `done` or `error`.
4. Present each output file as a saveable link so the user can keep it.

## Why async

Cowork's bash tool has a ~45-second hard timeout per call, and workflows take 2–8 minutes. Polling with short-lived requests keeps every bash call well under the cap.

## Step 0 — Make sure the server is running

**The workflow server runs on the user's Mac, in a Terminal window. Never try to start it yourself inside the sandbox — that doesn't work.**

Pick the base URL for your environment and health-check:

- **Cowork** (sandbox reaches the Mac via the docker bridge): `http://host.docker.internal:8100`
- **Claude Code** (running on the Mac directly): `http://localhost:8100`

```bash
# Cowork
curl -sS -m 3 http://host.docker.internal:8100/api/health
# Claude Code
curl -sS -m 3 http://localhost:8100/api/health
```

- If you get `{"status": "ok"}`: server is running, proceed.
- If you get connection refused: the user hasn't started the server yet. Ask them to:

  > Open Terminal, `cd` into the repo, and run: `bash start.sh`
  >
  > Leave the Terminal window open while we work.

  Wait for them to confirm, then re-run the health check before continuing.

Use the same base URL (`http://host.docker.internal:8100` or `http://localhost:8100`) for every subsequent call in the conversation.

## Step 1 — Kick off the workflow

Use bash with curl (use the URL confirmed in Step 0 — `host.docker.internal` for Cowork, `localhost` for Claude Code):

```bash
curl -sS -X POST <base-url>/api/<workflow_name> \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "<short page label>",
    "url": "<page URL if applicable>"
  }'
```

Response (HTTP 202):

```json
{
  "job_id": "a1b2c3d4...",
  "status": "pending",
  "poll_url": "/api/jobs/a1b2c3d4...",
  "hint": "Poll GET /api/jobs/<job_id> every 15–30s until status is 'done' or 'error'."
}
```

Save the `job_id`.

## Step 2 — Poll for completion

```bash
curl -sS <base-url>/api/jobs/<job_id>
```

Response will be one of:

- `{"status": "pending", ...}` — not started yet (rare; only right after POST)
- `{"status": "running", ...}` — in progress, keep polling
- `{"status": "done", "result": { ... full workflow output ... }}` — success
- `{"status": "error", "error": "message"}` — failed; show the error to the user

Between polls, wait 15–30 seconds. Don't poll faster — it adds no value and clutters the server log.

## Step 3 — Read the output files

When `status` is `done`, `result` has this shape:

```json
{
  "workflow": "page_audit",
  "topic": "...",
  "summary": "One-line summary",
  "content": "Full markdown report",
  "markdown_path": "outputs/page_audit/2026-04-22T...-slug.md",
  "json_path": "outputs/page_audit/2026-04-22T...-slug.json",
  "tracking_path": "tracking/runs.md"
}
```

`markdown_path` is relative to the repo root **on the user's Mac** (since the server runs there). It's already saved — the user can open it in Finder.

Read the markdown file and summarize the top findings for the user. Don't dump the full report in chat.

## Step 4 — Surface the output as a saveable link

Since the server runs on the user's Mac, output files land directly in the repo's `outputs/` folder on their machine. They can already open them in Finder — no sandbox copy step needed.

**In Claude Code:** present the file as a clickable markdown link to the local path, e.g. `[View your audit report](outputs/page_audit/2026-04-23T...-slug.md)`.

**In Cowork:** present the file as a `computer://` link to the Mac path, e.g. `[View your audit report](computer:///Users/<user>/repos/navi-marketing/outputs/page_audit/<timestamp>-<slug>.md)`. If you don't know the user's home path, ask — or use a relative path and tell them where it lives.

If a workflow produced two files (e.g., `internal_link_recommendations` produces both a report and a `_linked.md` version), present both as separate links. Name them clearly so the user knows what each one is.

Keep it concise: link-first, no long trailing explanation.

## Error handling

- **Connection refused**: server isn't running on the user's Mac. Ask them to open Terminal, `cd` into the repo, and run `bash start.sh`. Wait for confirmation, then re-run the health check.
- **404 on the job endpoint**: the server was restarted (in-memory job store was cleared). Re-run the workflow.
- **500 / status=error**: read the `error` field to the user. Common causes: missing API keys, Firecrawl rate limits, Drive fetch skipped so `artifacts/` was empty.
