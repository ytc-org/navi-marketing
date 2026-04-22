# Page Audit Skill

Audit a page against brand artifacts, real SERP competitor data, and content structure best practices.

## Prerequisites

1. **Server running.** See `skills/_shared/call-workflow.md` — Step 0 covers how to check the server and start it if needed.
2. **Fetch artifacts from Drive.** See `skills/_shared/fetch-artifacts.md`. Do this before calling the workflow unless you've already done it this conversation and the user hasn't mentioned editing Drive since.

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
curl -sS -X POST http://localhost:8100/api/page_audit \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "<short label>",
    "url": "<page URL>",
    "keywords": ["<optional>", "<keywords>"],
    "notes": "<optional context>"
  }'
```

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
