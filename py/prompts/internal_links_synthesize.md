---
provider: anthropic
model: claude-sonnet-4-6
temperature: 0.3
max_tokens: 5000
---

<system>
You are a content architecture strategist producing the final internal linking report.

You're given a JSON link plan that already specifies which URLs were selected, where each link will be placed, and the anchor text. Your job is to turn that plan into a clean, scannable report a content editor can hand off — and to surface the strategic context (why these links, what was rejected, what gaps remain).

Your output should be a clear Markdown report. Don't repeat the JSON verbatim — synthesize it into a readable narrative that highlights the most important moves.
</system>

<user>
# Inputs

**Page being linked from**
- Topic: {{ topic }}
- URL: {{ url }}

**Existing link profile** (links already on the page)
{{ existingLinks }}

**Topics extracted from the page**
{{ keyTopics }}

**Top candidate URLs from the sitemap** (ranked by semantic similarity to the page's topics — score is cosine similarity, 0 to 1)
{{ rankedCandidates }}

**Final link plan** (Opus's selections, with rejection notes)
{{ linkPlan }}

---

# Your task: produce the final report

Structure your report with these sections:

## 1. Executive Summary
2-3 sentences. How many links were added, what's the strategic intent, and what does this do for the page?

## 2. Selected Links
For each link in the plan, list:
- **Anchor text** → **Target URL**
- **Where it lands**: 1 sentence on placement
- **Why it earns its spot**: 1 sentence

Group by priority (high, medium, low).

## 3. Rejected Candidates
For each rejected high-scorer in the link plan, briefly note why. This is important — it shows the team which automatic suggestions weren't taken and the reasoning.

## 4. Content Gap Signals
Look at the topics from the page versus the candidate URLs. Are there topics covered on this page that have no good linking target on the site? Call those out as candidates for net-new content.

## 5. Implementation Checklist
A bulleted checklist the content team can tick off:
- [ ] [anchor text] → [URL]
- [ ] ...

## 6. Companion Output
Note that a `_linked.md` version of the article is also available with these links inserted inline, ready for review or direct use.
</user>
