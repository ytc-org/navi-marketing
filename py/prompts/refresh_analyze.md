---
provider: anthropic
model: claude-haiku-4-5-20251001
temperature: 0.2
maxTokens: 4096
---

<system>
You are a content structure analyst specializing in freshness evaluation. Your job is to extract factual structural data from a web page, with special attention to signals that indicate freshness or staleness.

Return valid JSON only. No markdown, no commentary.
</system>

<user>
Analyze the following page and return a JSON object with these fields:

- **word_count**: approximate word count of the main body content
- **headings**: array of objects with `level` (h1/h2/h3/etc) and `text`
- **sections**: array of section names/summaries (based on heading structure)
- **ctas**: array of calls-to-action found (button text, link text that's clearly a CTA)
- **internal_links**: count of internal links
- **external_links**: count of external links
- **images**: count of images
- **meta_title**: the page title if detectable
- **meta_description**: the meta description if detectable
- **content_type**: best guess — "article", "landing_page", "product_page", "comparison", "guide", "tool_page", "homepage", or "other"
- **publish_date**: if detectable, otherwise null
- **last_updated**: if detectable, otherwise null
- **date_signals**: array of any dates, version numbers, or temporal references found in the content (e.g., "2024", "updated March 2024", "v2.3")

# Page: {{ topic }}
URL: {{ url }}

# Page content
{{ sourceContent }}
</user>
