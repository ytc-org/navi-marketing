# Internal Link Recommendations Skill

Analyze a page, semantically rank links from the brand's own sitemap, have Opus pick the best ones, and produce both a recommendations report AND a ready-to-use linked version of the article.

## Prerequisites

1. **Server running.** See `skills/_shared/call-workflow.md` — Step 0 covers how to check the server and start it if needed.
2. **Verify local artifacts.** See `skills/_shared/fetch-artifacts.md`. Drive sync is disabled — just confirm the six files are present in `artifacts/`.
3. **OpenAI key required.** This workflow uses `OPENAI_API_KEY` for embeddings. If missing, the workflow will fail with a clear error pointing to setup.
4. **Fetch GSC top pages (recommended).** See `skills/_shared/fetch-gsc.md`. Pull the **last 90 days** of top pages site-wide (no URL filter). Opus uses this as a tiebreaker between similarly-relevant link candidates: when in doubt, link to a page that's a known high-traffic destination. If the source page has GSC data, also fetch its top queries to inform anchor-text choices.

## What to Ask the User

1. **URL** (required): "What page should I analyze for internal linking?"
2. **Sitemap URL** (optional): Defaults to `{domain}/sitemap.xml`. Ask only if the user's sitemap lives somewhere non-standard.
3. **Notes** (optional): Specific goals or pages to prioritize.

## Calling the Workflow

See `skills/_shared/call-workflow.md` for the async pattern.

**Kick off:**

```bash
# Top pages (site-wide) tiebreak link selection toward proven destinations.
# Optionally include top_queries for the source URL to inform anchor text.
GSC_JSON=$(jq -n '{
  property_url: "https://www.yournavi.com/",
  date_range: "last 90 days",
  page_url: "<source page URL>",
  top_queries: [ /* optional: top queries for the source page, for anchor-text inspiration */ ],
  top_pages:   [ /* 20–40 site-wide top pages from mcp__gsc__get_search_analytics, dimensions=page */ ]
}')

curl -sS -X POST http://localhost:8100/api/internal_link_recommendations \
  -H "Content-Type: application/json" \
  -d "$(jq -n \
        --arg topic "<short label>" \
        --arg url "<page URL>" \
        --argjson gsc "$GSC_JSON" \
        '{topic: $topic, url: $url, gsc: $gsc}')"
```

If the user has a custom sitemap URL, add `sitemap_url` to the body.
If GSC isn't available, omit `gsc` — link selection falls back to embedding similarity alone.

Expected runtime: **3–5 minutes.** Poll every 20–30s.

## What the Workflow Does (7 steps)

1. Fetch page content — Firecrawl or local file
2. Fetch & parse sitemap.xml (no LLM call). Follows sitemap indexes.
3. Extract existing links + topics (Haiku)
4. Embed + rank by similarity — OpenAI `text-embedding-3-small`, cosine similarity (top 30)
5. Opus selects and places 4–10 final links with anchor text and insertion points; notes rejected candidates
6. Sonnet inserts links into the article (`_linked.md`, body otherwise unchanged)
7. Sonnet synthesizes the recommendations report

## Outputs (two files per run)

- `outputs/internal_link_recommendations/<timestamp>-<slug>.md` — the recommendations report
- `outputs/internal_link_recommendations/<timestamp>-<slug>-linked.md` — the article with links inserted, ready to review or push live

## Presenting Results

Lead with: how many links were added, the top 3 highest-priority placements, and any content-gap signals (topics with no good internal target — candidates for net-new content). Link to both output files. Make it clear the `-linked.md` version is the article ready to use.
