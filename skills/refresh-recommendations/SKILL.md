# Refresh Recommendations Skill

Analyze an existing page and produce prioritized refresh recommendations — what to update, what's stale, and where competitors have newer content.

## Prerequisites

1. **Server running.** See `skills/_shared/call-workflow.md` — Step 0 covers how to check the server and start it if needed.
2. **Verify local artifacts.** See `skills/_shared/fetch-artifacts.md`. Drive sync is disabled — just confirm the six files are present in `artifacts/`.
3. **Fetch GSC trend data for the URL.** See `skills/_shared/fetch-gsc.md`. For refresh decisions, pull **last 90 days vs prior 90 days** and surface the deltas: what's losing clicks, what's losing position, and which queries used to rank but don't anymore. This is the heart of the refresh argument — without it, refresh recommendations are guesses about freshness rather than data-backed prioritization.

## What to Ask the User

1. **URL** (required): "What page needs a refresh check?"
2. **Topic** (optional): Short label. Derive from URL slug.
3. **Notes** (optional): Known issues, e.g., "Pricing changed last month."

URL alone is enough.

## Calling the Workflow

See `skills/_shared/call-workflow.md` for the async pattern.

**Kick off:**

```bash
# Build the structured GSC object — comparison is the heart of refresh decisions.
# Use mcp__gsc__compare_search_periods for the totals comparison; mcp__gsc__get_search_analytics for top queries.
GSC_JSON=$(jq -n '{
  property_url: "https://www.yournavi.com/",
  date_range: "last 90 days vs prior 90 days",
  page_url: "<page URL>",
  comparison: {
    period_label: "last 90d vs prior 90d",
    current: { clicks: 720, impressions: 24500, ctr: 0.0294, position: 11.8 },
    prior:   { clicks: 815, impressions: 23100, ctr: 0.0353, position: 9.6 }
  },
  top_queries: [ /* 15–25 rows for the URL, current period */ ],
  notes: "<biggest position drops + queries that lost ground>"
}')

curl -sS -X POST http://localhost:8100/api/refresh_recommendations \
  -H "Content-Type: application/json" \
  -d "$(jq -n \
        --arg topic "<short label>" \
        --arg url "<page URL>" \
        --argjson gsc "$GSC_JSON" \
        '{topic: $topic, url: $url, gsc: $gsc}')"
```

If GSC isn't available, omit `gsc` — the workflow falls back to freshness-only signals.

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
