# Net New Content Brief Skill

Create a comprehensive content brief for a brand-new article or page, grounded in competitive research and brand context. Optionally drafts the full article from the brief in the same call.

## Prerequisites

1. **Server running.** See `skills/_shared/call-workflow.md` — Step 0 covers how to check the server and start it if needed.
2. **Verify local artifacts.** See `skills/_shared/fetch-artifacts.md`. Drive sync is disabled — just confirm the six files are present in `artifacts/`.
3. **Fetch site-wide GSC queries that match the topic.** See `skills/_shared/fetch-gsc.md`. There's no URL yet, so don't filter to a page — instead, pull the **last 90 days** of site-wide queries containing the topic terms or target keywords. This shows what users *already* search for on the site adjacent to this topic, including queries Navi shows up for but doesn't have a dedicated page for (the strongest argument for net-new content). Skip if there's no obvious topical overlap with `yournavi.com`.

## What to Ask the User

1. **Topic** (required): "What's the topic for the new content?" — the working title or keyword cluster.
2. **Keywords** (optional): Target keywords if known.
3. **Audience** (optional): Who this content is for.
4. **Notes** (optional): Business goals, angle, specific requirements.
5. **Write the article too?** (optional): If yes, set `write_article: true`. Adds an Opus pass that drafts the full article from the brief. Adds ~3–5 min and noticeable cost — only do it when the user explicitly wants the article, not just the brief.

No URL needed — this is net-new content that doesn't exist yet.

## Calling the Workflow

See `skills/_shared/call-workflow.md` for the async pattern.

**Brief only:**

```bash
# Site-wide queries matching the topic — no page_url filter, since the page doesn't exist yet.
# Optionally include top_pages on adjacent topics to seed internal-link suggestions.
GSC_JSON=$(jq -n '{
  property_url: "https://www.yournavi.com/",
  date_range: "last 90 days",
  top_queries: [ /* site-wide queries containing the topic terms — argues for the page existing */ ],
  top_pages:   [ /* top adjacent pages — informs internal-link section of the brief */ ],
  notes: "<which adjacent queries the brand earns impressions for but lacks a dedicated page on>"
}')

curl -sS -X POST http://localhost:8100/api/net_new_content_brief \
  -H "Content-Type: application/json" \
  -d "$(jq -n \
        --arg topic "<working title or keyword cluster>" \
        --arg notes "<user angle / goals>" \
        --argjson keywords '["<target>","<keywords>"]' \
        --argjson gsc "$GSC_JSON" \
        '{topic: $topic, keywords: $keywords, notes: $notes, gsc: $gsc}')"
```

**Brief + drafted article:** add `write_article: true` to the JSON body above.

If there's no obvious topical overlap with `yournavi.com`, omit `gsc`.

Expected runtime: **2–4 minutes** for brief alone; **5–8 minutes** with `write_article`. Poll every 20–30s.

## What the Workflow Does

1. Research existing landscape — search and scrape top competitor pages
2. SERP analysis (Haiku) — H2 patterns, required topics, word count range, early-article priorities, gap opportunities
3. Gap identification (Sonnet) — what competitors miss
4. Brief generation (Opus) — writer-ready brief: title, outline, word count floor, differentiation angle, CTA strategy
5. Brand alignment review (Sonnet) — voice, personas, guardrails
6. Assemble final brief
7. Optional: draft full article (Opus) — when `write_article: true`, saves a separate `_article.md`

## Outputs

- `outputs/net_new_content_brief/<timestamp>-<slug>.md` — the brief (always)
- `outputs/net_new_content_brief/<timestamp>-<slug>-article.md` — the drafted article (only when `write_article: true`)

## Presenting Results

Lead with the recommended title, word count target, the differentiation angle, and the H2 outline. If `write_article` was used, also link to the article file and note it's a first draft to review, not final copy.
