# Net New Content Brief Skill

Create a comprehensive content brief for a brand-new article or page, grounded in competitive research and brand context. Optionally drafts the full article from the brief in the same call.

## Prerequisites

1. **Server running.** See `skills/_shared/call-workflow.md` — Step 0 covers how to check the server and start it if needed.
2. **Fetch artifacts from Drive.** See `skills/_shared/fetch-artifacts.md`.

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
curl -sS -X POST http://localhost:8100/api/net_new_content_brief \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "<working title or keyword cluster>",
    "keywords": ["<target>", "<keywords>"],
    "audience": "<optional>",
    "notes": "<optional angle / goals>"
  }'
```

**Brief + drafted article:**

```bash
curl -sS -X POST http://localhost:8100/api/net_new_content_brief \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "<working title or keyword cluster>",
    "keywords": ["<target>", "<keywords>"],
    "write_article": true
  }'
```

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
