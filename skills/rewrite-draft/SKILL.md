# Rewrite Draft Skill

Takes an existing page and produces a complete rewritten draft aligned with brand voice, competitive landscape, and content best practices.

## Prerequisites

1. **Server running.** See `skills/_shared/call-workflow.md` — Step 0 covers how to check the server and start it if needed.
2. **Verify local artifacts.** See `skills/_shared/fetch-artifacts.md`. Drive sync is disabled — just confirm the six files are present in `artifacts/`.
3. **Fetch GSC top queries for the URL.** See `skills/_shared/fetch-gsc.md`. For rewrites, pull the **last 90 days** of top queries for the specific URL — these are the searches the page is already winning impressions for, and the rewrite should preserve (or expand) that surface area, not accidentally drift away from it. Skip if the URL isn't on `yournavi.com` or the user is rewriting a local draft via `source_path`.

## What to Ask the User

1. **URL** (required): "What page should I rewrite?"
2. **Topic** (optional): Short label.
3. **Notes** (optional): Direction, e.g., "Focus on the pricing section" or "Make it more conversational."
4. **Audience** (optional): Only if the rewrite targets a different audience than the current page.

## Calling the Workflow

See `skills/_shared/call-workflow.md` for the async pattern.

**Kick off:**

```bash
# GSC top queries are the rewrite's "preserve list" — what the page is already winning.
GSC_JSON=$(jq -n '{
  property_url: "https://www.yournavi.com/",
  date_range: "last 90 days",
  page_url: "<page URL>",
  top_queries: [ /* 20–30 rows from mcp__gsc__get_search_analytics, dimensions=query, filtered to the URL */ ],
  notes: "<note any high-impression / low-CTR queries the rewrite should better address>"
}')

curl -sS -X POST http://localhost:8100/api/rewrite_draft \
  -H "Content-Type: application/json" \
  -d "$(jq -n \
        --arg topic "<short label>" \
        --arg url "<page URL>" \
        --arg notes "<user direction>" \
        --argjson gsc "$GSC_JSON" \
        '{topic: $topic, url: $url, notes: $notes, gsc: $gsc}')"
```

Skip `gsc` when rewriting a draft via `source_path` (no GSC data exists for an unpublished page).

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
