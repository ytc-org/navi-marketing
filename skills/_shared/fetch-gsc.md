# How to Fetch Google Search Console Data (shared pattern)

Several workflows are dramatically more useful when given real Google Search Console (GSC) data. Before calling those workflows, query the GSC MCP, build a structured `gsc` object, and pass it into the workflow's request body.

## Property to query

Navi's GSC property is **`https://www.yournavi.com/`** (URL-prefix property — note the `www.`). The service account has access only to this property; calls to `https://yournavi.com/` (no `www`) or other variants will return empty data.

If you ever want to confirm what's available, call `mcp__gsc__list_properties` first.

## When to fetch GSC data

Per-workflow guidance lives in each `SKILL.md`. The general rule:

- **Have a URL on `www.yournavi.com`?** Fetch page-level metrics + top queries filtered to that URL.
- **Net-new content (no URL yet)?** Fetch site-wide top queries matching the topic/keywords. Optionally fetch top pages on related topics for internal-link signals.
- **Off-domain URL** (a competitor, a draft from `source_path`, etc.): skip GSC.
- **Auditing the whole site for internal-link opportunities?** Fetch top pages site-wide.

## Step 1 — Verify the MCP is available

The MCP is registered as `gsc`. Tools you'll most often need:

- `mcp__gsc__list_properties` — confirms the property is reachable
- `mcp__gsc__get_performance_overview` — totals + daily trend for a property
- `mcp__gsc__get_search_analytics` — group-by-query / group-by-page / etc.
- `mcp__gsc__compare_search_periods` — current period vs prior, for trend deltas
- `mcp__gsc__get_search_by_page_query` — combined page+query slicing

If the GSC MCP tools aren't visible:

1. Ask the user to confirm `bash start.sh` has been run this session — `start.sh` registers the MCP if it's missing.
2. If still missing, instruct them: "Restart Claude Code so it picks up the newly registered MCP server."
3. If they've never run setup, point them to `setup.sh` to add their `GSC_CREDENTIALS_PATH`.
4. If GSC truly isn't available, **proceed with the workflow without GSC data** — call the workflow normally and skip the `gsc` field. The workflow will silently degrade.

## Step 2 — Pull the right data

Pick the smallest set of queries that answers what the workflow needs. Default windows:

| Workflow | Window | Pull |
|---|---|---|
| `page_audit` | last 28 days | page-level totals + top 15–25 queries filtered to the URL |
| `refresh_recommendations` | last 90 days vs prior 90 days | period comparison + top queries for the URL (current period) |
| `rewrite_draft` | last 90 days | top 20–30 queries for the URL |
| `metadata_suggestions` | last 90 days | top 20–30 queries by impressions for the URL |
| `net_new_content_brief` | last 90 days | site-wide top queries containing topic/keyword terms; optionally top pages on adjacent topics |
| `internal_link_recommendations` | last 90 days | top 20–40 pages site-wide |

## Step 3 — Build the `gsc` object

The workflow input accepts a structured `gsc` field. Shape (all fields optional — populate what you have):

```jsonc
{
  "property_url": "https://www.yournavi.com/",
  "date_range": "last 28 days (2026-04-08 to 2026-05-06)",
  "page_url": "https://www.yournavi.com/posts/best-prepaid-unlimited-plans",   // when filtered to a page
  "page_totals": {
    "clicks": 245,
    "impressions": 8420,
    "ctr": 0.029,           // 0.0–1.0 (not a percentage)
    "position": 12.4
  },
  "comparison": {
    "period_label": "last 90d vs prior 90d",
    "current": { "clicks": 720, "impressions": 24500, "ctr": 0.0294, "position": 11.8 },
    "prior":   { "clicks": 815, "impressions": 23100, "ctr": 0.0353, "position": 9.6 }
  },
  "top_queries": [
    { "query": "best prepaid unlimited plans", "clicks": 38, "impressions": 1245, "ctr": 0.030, "position": 6.2 },
    { "query": "navi prepaid",                 "clicks": 12, "impressions": 890,  "ctr": 0.013, "position": 8.1 }
  ],
  "top_pages": [
    { "page": "https://www.yournavi.com/coverage-map", "clicks": 1840, "impressions": 12500, "ctr": 0.147, "position": 3.0 }
  ],
  "notes": "High-impression / low-CTR flagged: 'navi prepaid' (890 imp, 1.3% CTR, pos 8.1) — title likely doesn't match intent."
}
```

A few rules:

- **CTR is a ratio, not a percent.** GSC returns `0.029`, not `2.9`. Pass it through as-is.
- **Don't fabricate fields** the MCP didn't return. If you didn't pull a comparison, omit it.
- **Trim to 15–30 rows.** More than that is noise; the prompt has a token budget.
- **Use `notes` for analyst commentary** — flag the high-impression / low-CTR queries, name the biggest losers in a comparison, etc. The workflow prompts read this.

## Step 4 — Call the workflow

Pass `gsc` alongside the usual fields. Build the JSON with `jq` (avoids quoting hell):

```bash
GSC_JSON=$(jq -n '
  {
    property_url: "https://www.yournavi.com/",
    date_range: "last 28 days",
    page_url: "https://www.yournavi.com/posts/best-prepaid-unlimited-plans",
    page_totals: { clicks: 245, impressions: 8420, ctr: 0.029, position: 12.4 },
    top_queries: [
      { query: "best prepaid unlimited plans", clicks: 38, impressions: 1245, ctr: 0.030, position: 6.2 }
    ],
    notes: "High-impression / low-CTR flagged: ..."
  }
')

curl -sS -X POST http://localhost:8100/api/page_audit \
  -H "Content-Type: application/json" \
  -d "$(jq -n \
        --arg topic "Best Prepaid Plans" \
        --arg url "https://www.yournavi.com/posts/best-prepaid-unlimited-plans" \
        --argjson gsc "$GSC_JSON" \
        '{topic: $topic, url: $url, gsc: $gsc}')"
```

When `gsc` is omitted (or set to `null`), the workflow runs exactly as it did before — GSC is purely additive.

## Step 5 — Mention what you fetched

In your reply to the user, briefly note the GSC window and the standout signal you flagged (e.g., "Pulled the last 28 days for this URL — flagged 'siri not working' as a high-impression / low-CTR opportunity"). This keeps them oriented and lets them ask for a different window or different filter if needed.
