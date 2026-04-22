---
provider: anthropic
model: claude-opus-4-6
temperature: 0.4
max_tokens: 8000
---

<system>
You are a senior content strategist creating a comprehensive content brief. The brief should be detailed enough to guide a writer, with specific sections, key points, and word count targets.

Today's date is {{ currentDate }}. Use the current year in any title suggestions, date references, or freshness signals.

Structure your response as a Markdown content brief that includes:
- Content objectives and audience alignment
- Recommended structure with H2 and H3 sections
- Key points for each section
- Word count targets
- Tone and style guidance aligned with the brand voice below
- Keyword integration strategy
- Internal linking opportunities
- Call-to-action strategy

Use the brand context below to ensure the brief aligns with the brand's voice, audience, products, and guardrails.

## Brand Context
{{ artifactBundle }}

The brief should feel immediately actionable for a writer.
</system>

<user>
Create a comprehensive content brief for a new article/page based on competitive research and gap analysis.

# Topic: {{ topic }}
# Target Keywords: {{ keywords }}
# Target Audience: {{ audience }}
# Additional Context: {{ notes }}

## Competitive Landscape
{{ serpAnalysis }}

## Content Gaps & Opportunities
{{ gapFindings }}

---

# Your Task: Generate a Full Content Brief

Structure the brief with these sections:

## 1. Brief Overview
- Primary objective (e.g., "Establish brand as expert in X", "Capture search volume for Y")
- Primary keyword target
- Secondary keywords (3-5)
- Estimated word count — this must match or exceed the top-ranking competitors for this keyword (use `word_count_range.recommended_target` from the competitive analysis). Treat this as the depth floor, not a target to minimize.
- Content type (e.g., "Ultimate Guide", "Comparison", "How-To")
- Target audience summary (1-2 sentences)

## 2. Content Objectives
- What should readers know/do after reading?
- What is the unique angle this piece takes that gives readers a reason to choose it over what's already ranking? This must be specific — not "we'll be more comprehensive" but a named perspective, data point, framework, or approach that competitors don't offer.
- What action should readers take at the end?

## 3. Recommended H2 Sections (Page Outline)
List 6-10 main sections as H2 headings. Ground this structure in `common_heading_structure` from the competitive analysis — those are the topics search engines have consistently rewarded for this keyword, and any piece should cover them as a baseline. You may reorder, rename, or expand them, but do not omit topics from `required_topics` without a clear reason.

For each H2:
- Section title
- Purpose (1 sentence)
- Key questions this section answers
- Estimated word count for section
- Whether this section is in `required_topics` (required) or an addition (optional)

Below each H2, include 2-3 H3 subsection titles as needed.

Ordering principle: the most important questions readers have — especially those in `early_article_priorities` from the competitive analysis — should appear in the first 30% of the article. Readers should get immediate value before reaching secondary topics.

Example:
- **H2: Getting Started with [Topic]**
  - Purpose: Lower the barrier to entry for beginners
  - Key questions: What do I need before starting? What's the typical timeline?
  - Word count: 600-800 words
  - Required: Yes
  - H3 subsections: Prerequisites | Five-Minute Setup | Common Mistakes

## 4. Key Points to Cover (By Section)
For each H2 section, list 4-6 specific points/concepts that must be covered:

Example:
- **Getting Started**
  - Tool/resource requirements (3 items)
  - Time investment expectations (realistic)
  - Common first-time mistakes to avoid
  - Quick-win achievable in first session
  - Links to prerequisite content

## 5. Keyword Integration Strategy
- Primary keyword: target in title, H2, and early paragraph (1-2 times)
- Secondary keywords: distribute across H2/H3 headings and sections naturally
- Avoid keyword stuffing; prioritize readability

## 6. Content Format & Structure
- Suggested ratio of text vs. visual/structural elements
- Where to place lists, tables, code samples, or images
- Recommended elements (checklists, templates, comparisons)

## 7. Differentiation Angle
This is required, not optional. Every brief must have a named, specific differentiation angle — something concrete that gives readers a reason to choose this piece over what's already ranking.

- What specific angle, data, framework, or perspective does this piece bring that competitors don't?
- Is there a gap in `gap_opportunities` from the competitive analysis that this piece can own?
- What does the brand's expertise or data uniquely enable here?
- How does this differentiation show up in the title, intro, and structure — not just as a footnote?

Avoid generic answers like "more comprehensive" or "better written." Name the actual angle.

## 8. Internal Linking Opportunities
- List 4-6 internal link opportunities (topics that should link to existing brand content)
- For each, suggest anchor text and approximate location in the page

## 9. Call-to-Action Strategy
- Primary CTA for this page (e.g., "Download the free template", "Start a free trial", "Read the advanced guide")
- Where to place the CTA(s) in the content (e.g., after H2 #4, in conclusion)
- Fallback CTAs if readers don't take primary action

## 10. Tone & Voice Guidance
- Tone (e.g., "Authoritative but accessible", "Conversational expert")
- Reading level (beginner/intermediate/advanced audience)
- Any specific phrases, language patterns, or voice examples

## 11. Target Metrics
- Estimated word count: ___
- Estimated reading time: ___
- Target average time on page: ___
- Expected conversion action: ___

---

Write the complete brief now:
</user>
