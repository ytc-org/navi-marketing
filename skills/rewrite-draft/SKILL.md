# Rewrite Draft Skill

Takes an existing page and produces a complete rewritten draft aligned with brand voice, competitive landscape, and content best practices.

## Prerequisites

1. **Server running.** See `skills/_shared/call-workflow.md` — Step 0 covers how to check the server and start it if needed.
2. **Fetch artifacts from Drive.** See `skills/_shared/fetch-artifacts.md`.

## What to Ask the User

1. **URL** (required): "What page should I rewrite?"
2. **Topic** (optional): Short label.
3. **Notes** (optional): Direction, e.g., "Focus on the pricing section" or "Make it more conversational."
4. **Audience** (optional): Only if the rewrite targets a different audience than the current page.

## Calling the Workflow

See `skills/_shared/call-workflow.md` for the async pattern.

**Kick off:**

```bash
curl -sS -X POST http://localhost:8100/api/rewrite_draft \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "<short label>",
    "url": "<page URL>",
    "notes": "<optional direction>"
  }'
```

Expected runtime: **3–5 minutes** (longer than other workflows because it writes a full draft). Poll every 20–30s.

## What the Workflow Does (7 steps)

1. Fetch page content
2. Content diagnosis — strengths, weaknesses, tone drift
3. Search and scrape top competitors for inspiration
4. Rewrite planning — keep, cut, add, restructure
5. Draft rewrite — full rewritten content in brand voice
6. Quality check — guardrails + keyword integration
7. Final assembly

## Presenting Results

The main deliverable is the rewritten draft in the `content` field. Summarize what changed and why, then link the user to the full file. The draft is publication-ready but should be reviewed by the content team.
