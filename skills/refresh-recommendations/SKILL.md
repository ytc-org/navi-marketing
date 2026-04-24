# Refresh Recommendations Skill

Analyze an existing page and produce prioritized refresh recommendations — what to update, what's stale, and where competitors have newer content.

## Prerequisites

1. **Server running.** See `skills/_shared/call-workflow.md` — Step 0 covers how to check the server and start it if needed.
2. **Verify local artifacts.** See `skills/_shared/fetch-artifacts.md`. Drive sync is disabled — just confirm the six files are present in `artifacts/`.

## What to Ask the User

1. **URL** (required): "What page needs a refresh check?"
2. **Topic** (optional): Short label. Derive from URL slug.
3. **Notes** (optional): Known issues, e.g., "Pricing changed last month."

URL alone is enough.

## Calling the Workflow

See `skills/_shared/call-workflow.md` for the async pattern.

**Kick off:**

```bash
curl -sS -X POST http://localhost:8100/api/refresh_recommendations \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "<short label>",
    "url": "<page URL>"
  }'
```

Expected runtime: **2–4 minutes.** Poll every 20–30s.

## What the Workflow Does (7 steps)

1. Fetch page content
2. Structural analysis — headings, word count, freshness signals
3. Freshness audit — outdated pricing, stale dates, old stats
4. Search and scrape top competitors
5. Competitive freshness comparison
6. Brand alignment check
7. Synthesize prioritized recommendations with effort estimates

## Presenting Results

Highlight: Executive Summary, Critical Refreshes (do now), Competitive Gaps to Close, Effort Estimates. Link to the saved file. Don't paste the full report into chat.
