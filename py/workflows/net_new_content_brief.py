#!/usr/bin/env python3
"""Net New Content Brief Workflow

Creates a comprehensive content brief for a brand-new article or page.
Researches the competitive landscape, analyzes SERP competitors, identifies
content gaps, and produces a detailed brief with structure, keywords, and
differentiation strategy validated against brand voice and guidelines.

Steps:
  1. Research existing landscape (search topic, scrape top 5 competitors)
  2. Analyze competitor content structure, depth, and coverage (Haiku)
  3. Identify content gaps and brand-unique angles (Sonnet)
  4. Generate full content brief with structure, keywords, sections (Sonnet)
  5. Review brief against brand voice and guardrails (Sonnet)
  6. Assemble final brief deliverable
  7. Persist output and tracking log

Usage (standalone):
  echo '{"topic": "Best Cloud Hosting Providers", "keywords": ["cloud hosting", "providers", "comparison"]}' | python py/workflows/net_new_content_brief.py

Usage (via server):
  POST http://localhost:8100/api/net_new_content_brief
  Body: {"topic": "Best Cloud Hosting Providers", "keywords": ["cloud hosting", "providers", "comparison"]}
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from lib.validation import WorkflowInput, WorkflowOutput
from lib.artifacts import load_artifacts, build_artifact_bundle
from lib.prompts import load_prompt, render_prompt
from lib.llm import call_claude
from lib.log import WorkflowLogger
from lib.scrape import search_and_scrape
from lib.persistence import persist_workflow_run, OUTPUTS_DIR, slugify, timestamp


def _parse_json_response(text: str) -> dict:
    """Try to parse JSON from an LLM response, handling markdown code fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {}


def run(workflow_input: WorkflowInput) -> WorkflowOutput:
    """Execute the net new content brief workflow."""

    log = WorkflowLogger("net_new_content_brief", total_steps=7)
    log.start(workflow_input.topic)

    # Validate that we have keywords or can infer them from topic
    search_keywords = workflow_input.keywords if workflow_input.keywords else [workflow_input.topic]

    # --- Step 1: Research existing landscape ---
    log.step("Researching existing landscape")
    log.detail(f"Using keywords: {search_keywords}")
    all_competitors: list[dict] = []
    seen_urls: set[str] = set()

    for query in search_keywords[:3]:
        log.detail(f"Searching & scraping: '{query}'")
        try:
            results = search_and_scrape(query, limit=5, scrape_content=True)

            for r in results:
                normalized = r.url.rstrip("/").lower()
                if normalized not in seen_urls:
                    seen_urls.add(normalized)
                    if r.content:
                        all_competitors.append({
                            "url": r.url,
                            "title": r.title,
                            "query": query,
                            "content": r.content[:12000],
                        })
        except Exception as e:
            log.warn(f"Error searching '{query}': {e}")

        if len(all_competitors) >= 8:
            break

    log.detail(f"Found {len(all_competitors)} unique competitor pages with content")
    log.step_done()

    # Format competitor content for analysis
    if all_competitors:
        competitor_sections = []
        for i, comp in enumerate(all_competitors[:8], 1):
            competitor_sections.append(
                f"### Competitor {i}: {comp['title']}\n"
                f"URL: {comp['url']}\n"
                f"Ranking for: {comp['query']}\n\n"
                f"{comp['content']}"
            )
        competitor_content = "\n\n---\n\n".join(competitor_sections)
    else:
        competitor_content = "No competitor content was retrieved. Proceed with general knowledge."

    # --- Step 2: SERP analysis ---
    log.step("Analyzing competitor content structure")
    serp_prompt = load_prompt("brief_serp_analysis")
    serp_rendered = render_prompt(
        serp_prompt,
        {
            "topic": workflow_input.topic,
            "keywords": ", ".join(search_keywords),
            "competitorContent": competitor_content,
        },
    )
    serp_analysis = call_claude(
        system=serp_rendered.system,
        user=serp_rendered.user,
        model=serp_rendered.config.model,
        temperature=serp_rendered.config.temperature,
        max_tokens=serp_rendered.config.max_tokens,
    )
    serp_data = _parse_json_response(serp_analysis)
    log.step_done("SERP analysis complete")

    # Load artifacts early — needed for gap analysis, brief generation, and brand review
    artifacts = load_artifacts()
    artifact_bundle = build_artifact_bundle(artifacts)

    # --- Step 3: Gap identification ---
    log.step("Identifying content gaps")
    gaps_prompt = load_prompt("brief_gaps")
    gaps_rendered = render_prompt(
        gaps_prompt,
        {
            "topic": workflow_input.topic,
            "keywords": ", ".join(search_keywords),
            "audience": workflow_input.audience or "Not specified",
            "serpAnalysis": json.dumps(serp_data, indent=2),
            "competitorContent": competitor_content,
            "artifactBundle": artifact_bundle,
        },
    )
    gap_findings = call_claude(
        system=gaps_rendered.system,
        user=gaps_rendered.user,
        model=gaps_rendered.config.model,
        temperature=gaps_rendered.config.temperature,
        max_tokens=gaps_rendered.config.max_tokens,
    )
    log.step_done("Gap analysis complete")

    # --- Step 4: Brief generation ---
    log.step("Generating content brief")
    brief_prompt = load_prompt("brief_generate")
    brief_rendered = render_prompt(
        brief_prompt,
        {
            "topic": workflow_input.topic,
            "keywords": ", ".join(search_keywords),
            "audience": workflow_input.audience or "Not specified",
            "notes": workflow_input.notes or "None",
            "currentDate": __import__("datetime").date.today().isoformat(),
            "serpAnalysis": json.dumps(serp_data, indent=2),
            "gapFindings": gap_findings,
            "artifactBundle": artifact_bundle,
        },
    )
    generated_brief = call_claude(
        system=brief_rendered.system,
        user=brief_rendered.user,
        model=brief_rendered.config.model,
        temperature=brief_rendered.config.temperature,
        max_tokens=brief_rendered.config.max_tokens,
    )
    log.step_done("Brief generation complete")

    # --- Step 5: Brand alignment review ---
    log.step("Reviewing brand alignment")
    review_prompt = load_prompt("brief_brand_review")
    review_rendered = render_prompt(
        review_prompt,
        {
            "topic": workflow_input.topic,
            "brief": generated_brief,
            "artifactBundle": artifact_bundle,
        },
    )
    brand_review = call_claude(
        system=review_rendered.system,
        user=review_rendered.user,
        model=review_rendered.config.model,
        temperature=review_rendered.config.temperature,
        max_tokens=review_rendered.config.max_tokens,
    )
    log.step_done("Brand alignment review complete")

    # --- Step 6: Assemble final brief ---
    log.step("Assembling final brief")
    from datetime import date
    today = date.today().isoformat()

    # Build a readable competitor landscape summary instead of raw JSON
    landscape_lines = []
    if serp_data:
        for key in ["common_heading_structure", "content_types_found", "common_topics_covered",
                     "unique_angles_observed", "missing_or_light_topics"]:
            items = serp_data.get(key, [])
            if items:
                label = key.replace("_", " ").title()
                landscape_lines.append(f"### {label}")
                for item in items[:10]:
                    if isinstance(item, dict):
                        topic_name = item.get("topic", str(item))
                        depth = item.get("depth", "")
                        landscape_lines.append(f"- {topic_name}" + (f" ({depth})" if depth else ""))
                    else:
                        landscape_lines.append(f"- {item}")
                landscape_lines.append("")
        avg_wc = serp_data.get("average_word_count", "Unknown")
        landscape_lines.append(f"**Average competitor word count**: {avg_wc}")
    else:
        landscape_lines.append("No SERP analysis data available.")
    landscape_summary = "\n".join(landscape_lines)

    # Build competitor URL list
    comp_urls = "\n".join([f"- [{c['title']}]({c['url']})" for c in all_competitors[:8]])

    final_brief = f"""# Content Brief: {workflow_input.topic}

**Date**: {today}
**Keywords**: {", ".join(search_keywords)}
**Audience**: {workflow_input.audience or "General"}
**Competitors analyzed**: {len(all_competitors)}

---

## Competitive Landscape Analysis

{landscape_summary}

---

## Content Gaps & Opportunities

{gap_findings}

---

## Content Brief

{generated_brief}

---

## Brand Alignment Review

{brand_review}

---

## Competitors Analyzed

{comp_urls}
"""

    # --- Optional step: write full article from the brief ---
    article_path_relative: str | None = None
    if workflow_input.write_article:
        log.detail("Drafting full article from brief (Opus)")
        article_prompt = load_prompt("brief_write_article")
        article_rendered = render_prompt(
            article_prompt,
            {
                "topic": workflow_input.topic,
                "keywords": ", ".join(search_keywords),
                "audience": workflow_input.audience or "General",
                "currentDate": today,
                "brief": generated_brief,
                "artifactBundle": artifact_bundle,
            },
        )
        article_draft = call_claude(
            system=article_rendered.system,
            user=article_rendered.user,
            model=article_rendered.config.model,
            temperature=article_rendered.config.temperature,
            max_tokens=article_rendered.config.max_tokens,
        )
        # Save article alongside the brief
        slug = workflow_input.output_slug or slugify(workflow_input.topic)
        stamp = timestamp()
        article_dir = OUTPUTS_DIR / "net_new_content_brief"
        article_dir.mkdir(parents=True, exist_ok=True)
        article_path = article_dir / f"{stamp}-{slug}-article.md"
        header = "\n".join([
            f"# {workflow_input.topic}",
            "",
            f"_Drafted from brief on {today}. Keywords: {', '.join(search_keywords)}._",
            "",
            "---",
            "",
        ])
        article_path.write_text(header + article_draft.strip() + "\n", encoding="utf-8")
        article_path_relative = f"outputs/net_new_content_brief/{article_path.name}"
        # Append a pointer to the article into the brief itself
        final_brief = final_brief + f"\n\n---\n\n## Drafted Article\n\nA full article drafted from this brief is available at: `{article_path_relative}`\n"
        log.detail(f"Article saved to {article_path_relative}")

    log.step_done()

    # --- Step 7: Persist ---
    log.step("Saving output")
    output = persist_workflow_run(
        workflow_name="net_new_content_brief",
        workflow_input=workflow_input,
        content=final_brief,
        json_data={
            "workflowType": "net-new-content-brief",
            "topic": workflow_input.topic,
            "keywords": search_keywords,
            "audience": workflow_input.audience or "General",
            "competitors_analyzed": [
                {"url": c["url"], "title": c["title"], "query": c["query"]}
                for c in all_competitors
            ],
            "serp_analysis": serp_data,
            "article_path": article_path_relative,
            "steps": {
                "gap_findings": gap_findings,
                "generated_brief": generated_brief,
                "brand_review": brand_review,
            },
        },
    )

    if article_path_relative:
        log.detail(f"Article: {article_path_relative}")
    log.step_done()
    log.done(output.markdown_path)
    return output


def main() -> None:
    """CLI entry point — reads JSON from stdin."""
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(PROJECT_ROOT / "py"))

    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")

    raw = sys.stdin.read().strip()
    if not raw:
        print("Error: provide input as JSON on stdin.", file=sys.stderr)
        print(
            'Example: echo \'{"topic": "Best Cloud Hosting", "keywords": ["cloud hosting", "providers"]}\' '
            "| python py/workflows/net_new_content_brief.py",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON input: {e}", file=sys.stderr)
        sys.exit(1)

    workflow_input = WorkflowInput(**data)
    output = run(workflow_input)
    print(json.dumps(output.model_dump(), indent=2))


if __name__ == "__main__":
    main()
