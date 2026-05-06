# Metadata Suggestions Skill

Generate optimized title tags, meta descriptions, heading structures, and on-page SEO guidance for a page.

## Prerequisites

1. **Server running.** See `skills/_shared/call-workflow.md` — Step 0 covers how to check the server and start it if needed.
2. **Verify local artifacts.** See `skills/_shared/fetch-artifacts.md`. Drive sync is disabled — just confirm the six files are present in `artifacts/`.
3. **Fetch GSC top queries for the URL.** See `skills/_shared/fetch-gsc.md`. For metadata work, pull the **last 90 days** of top queries by *impressions* for the URL, plus their CTRs. These are the highest-leverage signals for title/meta optimization: high-impression / low-CTR queries point directly at messaging mismatches the new title and description should fix.

## What to Ask the User

1. **URL** (required): "What page needs metadata optimization?"
2. **Keywords** (optional): Target keywords if the user has specific ones in mind.

URL alone is enough — the workflow extracts keywords automatically.

## Calling the Workflow

See `skills/_shared/call-workflow.md` for the async pattern.

**Kick off:**

```bash
# Sort top queries by impressions (not clicks) — those are the unfulfilled-demand signal.
GSC_JSON=$(jq -n '{
  property_url: "https://www.yournavi.com/",
  date_range: "last 90 days",
  page_url: "<page URL>",
  top_queries: [ /* 20–30 rows for the URL, sorted by impressions desc */ ],
  notes: "<flag specific high-impression / low-CTR queries — these are the title/meta opportunities>"
}')

curl -sS -X POST http://localhost:8100/api/metadata_suggestions \
  -H "Content-Type: application/json" \
  -d "$(jq -n \
        --arg topic "<short label>" \
        --arg url "<page URL>" \
        --argjson gsc "$GSC_JSON" \
        '{topic: $topic, url: $url, gsc: $gsc}')"
```

If GSC isn't available, omit `gsc` — the workflow falls back to SERP scrape data only.

Expected runtime: **1–2 minutes** (faster than other workflows — uses search metadata only, not full competitor page scraping). Poll every 15s.

## What the Workflow Does (6 steps)

1. Fetch page content
2. Extract current metadata — title, description, headings, schema, OG tags
3. Keyword analysis — primary/secondary, placement, density
4. Search SERP landscape — competitor titles and descriptions (metadata only)
5. Generate options — 3 title tags, 3 meta descriptions, optimized headings
6. Synthesize — final recommendations with character counts and rationale

## Presenting Results

Lead with the recommended title tag and meta description (the most actionable items). Then heading structure and schema suggestions. Include character counts. Link to the full file.
