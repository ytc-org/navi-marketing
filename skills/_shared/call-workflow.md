# How to Call a Workflow (shared pattern)

All workflows are async. The flow is:

1. Make sure the workflow server is running (start it if needed).
2. `POST /api/<workflow>` — returns a `job_id` immediately.
3. `GET /api/jobs/<job_id>` — poll every 15–30 seconds until `status` is `done` or `error`.
4. Present each output file as a saveable link so the user can keep it.

## Why async

Workflows take 2–8 minutes. Polling with short-lived requests keeps every bash call fast and lets the user see progress.

## Step 0 — Make sure the server is running

The workflow server runs on the user's Mac in a Terminal window, reachable at `http://localhost:8100`.

```bash
curl -sS -m 3 http://localhost:8100/api/health
```

- If you get `{"status": "ok"}`: server is running, proceed.
- If you get connection refused: the user hasn't started the server yet. Ask them to:

  > Open Terminal, `cd` into the repo, and run: `bash start.sh`
  >
  > Leave the Terminal window open while we work.

  Wait for them to confirm, then re-run the health check before continuing.

## Step 1 — Kick off the workflow

Use bash with curl:

```bash
curl -sS -X POST http://localhost:8100/api/<workflow_name> \
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
curl -sS http://localhost:8100/api/jobs/<job_id>
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

Output files land in the repo's `outputs/` folder on the user's Mac. Present each one as a clickable markdown link to the local path, e.g. `[View your audit report](outputs/page_audit/2026-04-23T...-slug.md)`.

If a workflow produced two files (e.g., `internal_link_recommendations` produces both a report and a `_linked.md` version), present both as separate links. Name them clearly so the user knows what each one is.

Keep it concise: link-first, no long trailing explanation.

## Error handling

- **Connection refused**: server isn't running on the user's Mac. Ask them to open Terminal, `cd` into the repo, and run `bash start.sh`. Wait for confirmation, then re-run the health check.
- **404 on the job endpoint**: the server was restarted (in-memory job store was cleared). Re-run the workflow.
- **500 / status=error**: read the `error` field to the user. Common causes: missing API keys, Firecrawl rate limits, empty `artifacts/` folder.
