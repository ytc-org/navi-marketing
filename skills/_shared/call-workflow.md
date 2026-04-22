# How to Call a Workflow (shared pattern)

All workflows are async. The flow is:

1. Make sure the workflow server is running (start it if needed).
2. `POST /api/<workflow>` — returns a `job_id` immediately.
3. `GET /api/jobs/<job_id>` — poll every 15–30 seconds until `status` is `done` or `error`.
4. Present each output file as a saveable link so the user can keep it.

## Why async

Cowork's bash tool has a ~45-second hard timeout per call, and workflows take 2–8 minutes. Polling with short-lived requests keeps every bash call well under the cap.

## Step 0 — Make sure the server is running

The Python workflow server runs inside the Cowork bash sandbox. Check if it's already up before each session:

```bash
curl -sS -m 3 http://localhost:8100/api/health
```

- If you get `{"status": "ok"}`: server is running, proceed.
- If you get connection refused: start it.

To start the server, use bash with `nohup` and a log file so it persists across bash calls:

```bash
cd <path to the repo inside the sandbox, e.g. /sessions/.../mnt/repos/navi-marketing>
nohup python3 py/server.py > /tmp/wf-server.log 2>&1 &
# wait a couple seconds, then health-check
sleep 3
curl -sS -m 3 http://localhost:8100/api/health
```

The repo path in the sandbox is whatever `request_cowork_directory` returned when the user connected the repo folder. If the user hasn't connected the repo folder yet, ask them to do it.

**Note:** Since the server runs inside the sandbox, its outputs also live in the sandbox — they're not saved to the user's Mac automatically. See Step 4 for how to surface outputs.

**Advanced case — user already runs the server themselves.** Some users start `python3 py/server.py` on their Mac directly so outputs land in their local `outputs/` folder. In that case, the server is reachable at `http://host.docker.internal:8100` instead of `localhost`. If `curl http://localhost:8100/api/health` fails but `curl http://host.docker.internal:8100/api/health` works, use that URL for all subsequent calls in the conversation.

## Step 1 — Kick off the workflow

Use `mcp__workspace__bash` with curl (use the URL confirmed in Step 0):

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

`markdown_path` is relative to the repo root (inside the sandbox if you started the server there, or on the user's Mac if they started it themselves).

Read the markdown file and summarize the top findings for the user. Don't dump the full report in chat.

## Step 4 — Surface the output as a saveable link (important)

Users can't browse the sandbox filesystem — they need the file presented back to them explicitly. For each output file the workflow produced:

1. Copy the file into the session's outputs directory (the user-visible scratchpad).
2. Present a link to that copy using Cowork's file-sharing pattern.

Example:

```bash
cp /sessions/.../mnt/repos/navi-marketing/outputs/page_audit/<timestamp>-<slug>.md \
   /sessions/.../mnt/outputs/<timestamp>-<slug>.md
```

Then in chat, share it like:

```
[View your audit report](computer:///Users/.../outputs/<timestamp>-<slug>.md)
```

If a workflow produced two files (e.g., `internal_link_recommendations` produces both a report and a `_linked.md` version), present both as separate links. Name them clearly so the user knows what each one is.

Follow the file-sharing rules from the Cowork environment: concise, link-first, no long trailing explanation. The user can preview the file and decide where to save it.

## Error handling

- **Connection refused**: server isn't running. Go back to Step 0 and start it.
- **404 on the job endpoint**: the server was restarted (in-memory job store was cleared). Re-run the workflow.
- **500 / status=error**: read the `error` field to the user. Common causes: missing API keys, Firecrawl rate limits, Drive fetch skipped so `artifacts/` was empty.
