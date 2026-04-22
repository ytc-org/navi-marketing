---
provider: anthropic
model: claude-haiku-4-5-20251001
temperature: 0.1
maxTokens: 2000
---

<system>
You are a metadata extraction specialist. Your job is to identify and extract all existing SEO metadata from a page.

Return valid JSON only. No markdown, no commentary.
</system>

<user>
Extract all current metadata from this page and return a JSON object with:

- **title_tag**: The page's <title> tag content (if present)
- **meta_description**: The <meta name="description"> content (if present)
- **h1**: The page's H1 heading text (if present)
- **h2_headings**: Array of all H2 heading texts on the page
- **canonical_url**: The canonical URL if set (from <link rel="canonical">)
- **og_title**: Open Graph title tag (if present)
- **og_description**: Open Graph description (if present)
- **og_image**: Open Graph image URL (if present)
- **schema_markup**: Brief summary of any structured data (JSON-LD, schema.org) found
- **current_title_length**: Character count of the title tag
- **current_description_length**: Character count of the meta description
- **issues**: Array of any metadata problems detected (missing title, duplicate H1s, description too short, etc.)

# Page: {{ topic }}
URL: {{ url }}

# Page content
{{ sourceContent }}
</user>
