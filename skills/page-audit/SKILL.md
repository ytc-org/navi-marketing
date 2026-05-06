# Page Audit Skill

Audit a page against brand artifacts, real SERP competitor data, and content structure best practices.

## Prerequisites

1. **Server running.** See `skills/_shared/call-workflow.md` — Step 0 covers how to check the server and start it if needed.
2. **Verify local artifacts.** See `skills/_shared/fetch-artifacts.md`. Confirm `artifacts/` has the six expected files before calling the workflow. Drive sync is disabled — do not fetch from Google Drive.
3. **Fetch GSC data for the URL.** See `skills/_shared/fetch-gsc.md`. For page audits, pull the **last 28 days**: page-level totals (clicks, impressions, CTR, position) plus the top 15–25 queries for the specific URL. The workflow will use this to spot title/CTR mismatches, ranking decay, and queries the page should rank for but doesn't. Skip if the URL isn't on `yournavi.com` (e.g., auditing a draft via `source_path`).

## What to Ask the User

1. **URL** (required): "What page should I audit?"
2. **Topic** (optional): Short label. Derive from the URL slug if not given.
3. **Keywords** (optional): Target keywords. Workflow extracts them automatically if omitted.
4. **Audience** (optional): Falls back to brand artifacts if omitted.
5. **Notes** (optional): Specific concerns, e.g., "Losing rank to competitor X."

Don't over-ask — URL alone is enough.

## Calling the Workflow

See `skills/_shared/call-workflow.md` for the full async pattern (POST → poll `/api/jobs/<id>`).

**Kick off:**

```bash
# Build the structured GSC object first (see skills/_shared/fetch-gsc.md)
GSC_JSON=$(jq -n '{
  property_url: "https://www.yournavi.com/",
  date_range: "last 28 days",
  page_url: "<page URL>",
  page_totals: { clicks: 245, impressions: 8420, ctr: 0.029, position: 12.4 },
  top_queries: [ /* 15–25 rows from mcp__gsc__get_search_analytics, dimensions=query, filtered to the URL */ ],
  notes: "<flag any high-impression / low-CTR queries here>"
}')

curl -sS -X POST http://localhost:8100/api/page_audit \
  -H "Content-Type: application/json" \
  -d "$(jq -n \
        --arg topic "<short label>" \
        --arg url "<page URL>" \
        --arg notes "<user notes>" \
        --argjson gsc "$GSC_JSON" \
        '{topic: $topic, url: $url, notes: $notes, gsc: $gsc}')"
```

If GSC isn't available, omit the `gsc` field — the workflow degrades silently.

Expected runtime: **2–5 minutes.** Poll every 20–30s.

### Input fields

- `topic` (string, required): Short label for the page
- `url` (string): Page URL — needed for scraping and competitor comparison
- `keywords` (string[]): Target keywords
- `audience` (string): Target audience description
- `notes` (string): Extra context or concerns
- `source_path` (string): Local file path if auditing a draft instead of a live URL

## What the Workflow Does (7 steps)

1. Fetch page content via Firecrawl
2. Structural analysis — headings, word count, CTAs, links, meta tags
3. Extract primary/secondary keywords and generate search queries
4. Search & scrape top competitor pages (up to 8)
5. Brand evaluation — style, audience, guardrails, product accuracy
6. Competitive gap analysis — coverage, structure, depth
7. Synthesize final prioritized report

## Response Format

When the job reaches `status: "done"`, `result` contains:

```json
{
  "workflow": "page_audit",
  "topic": "...",
  "summary": "One-line summary",
  "content": "Full markdown audit report",
  "markdown_path": "outputs/page_audit/<timestamp>-<slug>.md",
  "json_path": "outputs/page_audit/<timestamp>-<slug>.json",
  "tracking_path": "tracking/runs.md"
}
```

## Presenting Results

1. Don't dump the full report in chat. Read `markdown_path` and summarize the top findings.
2. Highlight: Executive Summary, Critical Issues, Search Intent Gaps, Next Steps.
3. Link the user to the saved file so they can read the rest.
