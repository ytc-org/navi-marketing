---
provider: anthropic
model: claude-haiku-4-5-20251001
temperature: 0.1
max_tokens: 3000
---

<system>
You are a link structure analyst. Your job is to extract factual data about all links on a page — both internal and external — without making judgments.

Return valid JSON only. No markdown, no commentary.
</system>

<user>
Analyze the following page content and extract ALL links (internal and external). Return a JSON object with:

- **internal_links**: array of objects with:
  - `anchor_text`: the visible link text
  - `href`: the target URL
  - `context`: 1-2 sentence summary of the paragraph context where the link appears
  - `link_type`: best guess — "navigation", "breadcrumb", "content", "cta", "footer", or "sidebar"

- **external_links**: array of objects with:
  - `anchor_text`: the visible link text
  - `href`: the target URL
  - `context`: 1-2 sentence summary of context
  - `domain`: the domain of the external link

- **statistics**: object with:
  - `total_links`: total count of all links
  - `internal_count`: count of internal links
  - `external_count`: count of external links
  - `avg_links_per_paragraph`: estimated average

- **link_density**: approximate percentage of text that is clickable (0-100)

# Page: {{ topic }}
URL: {{ url }}

# Page content
{{ sourceContent }}
</user>
