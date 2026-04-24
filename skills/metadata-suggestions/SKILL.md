# Metadata Suggestions Skill

Generate optimized title tags, meta descriptions, heading structures, and on-page SEO guidance for a page.

## Prerequisites

1. **Server running.** See `skills/_shared/call-workflow.md` — Step 0 covers how to check the server and start it if needed.
2. **Verify local artifacts.** See `skills/_shared/fetch-artifacts.md`. Drive sync is disabled — just confirm the six files are present in `artifacts/`.

## What to Ask the User

1. **URL** (required): "What page needs metadata optimization?"
2. **Keywords** (optional): Target keywords if the user has specific ones in mind.

URL alone is enough — the workflow extracts keywords automatically.

## Calling the Workflow

See `skills/_shared/call-workflow.md` for the async pattern.

**Kick off:**

```bash
curl -sS -X POST http://localhost:8100/api/metadata_suggestions \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "<short label>",
    "url": "<page URL>",
    "keywords": ["<optional>"]
  }'
```

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
