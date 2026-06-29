# GSC Reports & Dashboards Skill

Generate ranking reports and visual dashboards straight from Google Search Console — **no
content workflow or Python server involved.** This is just Claude talking to the GSC MCP,
pulling data, and turning it into an HTML dashboard or table you can open in a browser.

Use this when the user wants to *see how things are ranking* — "where do all our blog posts
rank," "what dropped this month," "mobile vs. desktop," "build me a dashboard" — as opposed
to auditing or rewriting a specific page (those are the `page_audit` / `refresh` workflows).

## Prerequisites

1. **GSC MCP available.** Tools are named `mcp__gsc__*`. If they're not visible, see
   `skills/_shared/fetch-gsc.md` → "Verify the MCP is available" (needs `./credentials.json`
   at the repo root + `bash start.sh`, then a Claude Code restart).
2. **Property:** Navi's is `https://www.yournavi.com/` (URL-prefix, **with** `www.`). Calls
   to the non-`www` variant return empty data. Confirm with `mcp__gsc__list_properties` if
   unsure.
3. The blog lives under `/posts/` — filter to that path for "blog rankings."

## Core MCP tools

| Tool | Use for |
|------|---------|
| `mcp__gsc__get_performance_overview` | Site totals + daily trend |
| `mcp__gsc__get_search_analytics` | Group by query / page / date / device / country |
| `mcp__gsc__get_advanced_search_analytics` | Same, with filtering, sorting, row limits |
| `mcp__gsc__compare_search_periods` | Period-over-period deltas (movers) |
| `mcp__gsc__get_search_by_page_query` | Page + query combined slicing |
| `mcp__gsc__inspect_url_enhanced` / `batch_url_inspection` | Index status for specific URLs |

## Report recipes

Pick the one that matches the ask, pull the data, then render (see "Rendering" below).

### 1. "Where does everything rank right now"
Pull the last 28 days grouped by **page** (and optionally by query), filtered to `/posts/`.
Sort by impressions or clicks. Columns: page, top query, clicks, impressions, CTR, avg
position. This is the at-a-glance ranking table Chris was building by hand across ~500 URLs.

### 2. Mobile vs. desktop
Run the page-level pull **twice** with a device filter (`MOBILE`, then `DESKTOP`) via
`get_advanced_search_analytics`, then join on page so each row shows desktop position vs.
mobile position side by side. Highlight pages where mobile lags desktop by >3 positions.

### 3. Movers (what changed)
`compare_search_periods` — last 28 days vs. prior 28 (or 90 vs. 90). Surface biggest
position drops and click losses (refresh candidates) and biggest gains. Sort by absolute
delta.

### 4. Opportunity finder
`get_search_analytics` by query, then filter client-side to **position 8–20 with high
impressions** (almost page one) and **high impressions / low CTR** (title/meta mismatch).
These are the fastest wins.

### 5. Indexing health
`batch_url_inspection` over a list of URLs (e.g. from the sitemap) to flag anything not
indexed or excluded.

## Data-volume tips

- The full click dataset can be tens of thousands of rows. Pull **aggregated** (grouped)
  data, not raw rows, and cap row counts (e.g. top 200 pages). If a single call returns too
  much, narrow the date range or add a path/device filter rather than fetching everything.
- CTR comes back as a ratio (`0.029`), not a percent. Multiply by 100 only at render time.
- Save the pulled data to a file under the scratchpad or `outputs/` before rendering so a
  re-render doesn't require re-querying GSC.

## Rendering

Default to an **HTML dashboard** — it's far more useful than a wall of text. Have Claude
write the pulled data to a JSON/CSV file, then generate a self-contained `.html` (inline CSS,
a sortable table, and a couple of summary cards / simple charts) and save it to `outputs/`.
Open it in a browser. For a quick look, a Markdown table is fine.

Ask the user what they want before rendering if it's ambiguous: time window, blog-only vs.
whole site, which metric to sort by, and dashboard vs. table.

## What this skill does NOT do

- It doesn't write to GSC or change rankings — read-only reporting.
- For auditing/rewriting a *specific* page, use the `page_audit` or `rewrite_draft`
  workflows (which can also take a `gsc` slice — see `skills/_shared/fetch-gsc.md`).
