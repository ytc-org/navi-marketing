#!/usr/bin/env python3
"""Refresh Recommendations Workflow

Analyzes a page and produces prioritized refresh recommendations. Identifies
outdated content, competitive gaps, and freshness issues.

Steps:
  1. Fetch page content (Firecrawl or local file)
  2. Structural analysis (Haiku) — word count, headings, freshness signals
  3. Freshness audit (Haiku) — outdated info, stale references, date issues
  4. Search competitor landscape and scrape top 5 pages
  5. Competitive freshness comparison (Sonnet) — compare depth/freshness vs competitors
  6. Brand alignment check (Sonnet) — evaluate voice/tone drift, audience mismatch
  7. Synthesize prioritized refresh recommendations (Sonnet)
  8. Persist output and tracking log

Usage (standalone):
  echo '{"topic": "Pricing Guide", "url": "https://example.com/pricing"}' | python py/workflows/refresh_recommendations.py

Usage (via server):
  POST http://localhost:8100/api/refresh_recommendations
  Body: {"topic": "Pricing Guide", "url": "https://example.com/pricing"}
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from lib.validation import WorkflowInput, WorkflowOutput
from lib.artifacts import load_artifacts, build_artifact_bundle, read_source_file
from lib.prompts import load_prompt, render_prompt
from lib.llm import call_claude
from lib.scrape import scrape_page, search_and_scrape
from lib.persistence import persist_workflow_run


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
    """Execute the refresh recommendations workflow. Called by the server or standalone."""

    print(f"[refresh_recommendations] Starting workflow: {workflow_input.topic}")

    # --- Step 1: Get source content ---
    print("[refresh_recommendations] Step 1/7: Fetching page content...")
    source_content = read_source_file(workflow_input.source_path)
    if not source_content and workflow_input.url:
        source_content = scrape_page(workflow_input.url)
    if not source_content:
        raise ValueError("No source content available. Provide a URL or source_path.")
    print(f"  Got {len(source_content)} chars of content.")

    # --- Step 2: Structural analysis ---
    print("[refresh_recommendations] Step 2/7: Analyzing content structure...")
    analyze_prompt = load_prompt("refresh_analyze")
    analyze_rendered = render_prompt(
        analyze_prompt,
        {
            "topic": workflow_input.topic,
            "url": workflow_input.url or "Not provided",
            "sourceContent": source_content,
        },
    )
    structural_analysis = call_claude(
        system=analyze_rendered.system,
        user=analyze_rendered.user,
        model=analyze_rendered.config.model,
        temperature=analyze_rendered.config.temperature,
        max_tokens=analyze_rendered.config.max_tokens,
    )
    structural_data = _parse_json_response(structural_analysis)
    print("  Structural analysis complete.")

    # --- Step 3: Freshness audit ---
    print("[refresh_recommendations] Step 3/7: Auditing content freshness...")
    freshness_prompt = load_prompt("refresh_freshness")
    freshness_rendered = render_prompt(
        freshness_prompt,
        {
            "topic": workflow_input.topic,
            "url": workflow_input.url or "Not provided",
            "sourceContent": source_content,
            "structuralAnalysis": json.dumps(structural_data, indent=2),
        },
    )
    freshness_audit = call_claude(
        system=freshness_rendered.system,
        user=freshness_rendered.user,
        model=freshness_rendered.config.model,
        temperature=freshness_rendered.config.temperature,
        max_tokens=freshness_rendered.config.max_tokens,
    )
    freshness_data = _parse_json_response(freshness_audit)
    print("  Freshness audit complete.")

    # --- Step 4: Search and scrape competitor pages ---
    print("[refresh_recommendations] Step 4/7: Searching and scraping competitor pages...")
    all_competitors: list[dict] = []
    seen_urls: set[str] = set()
    target_url = (workflow_input.url or "").rstrip("/").lower()

    # Use provided keywords or extract from topic
    search_keywords = workflow_input.keywords or [workflow_input.topic]
    if not search_keywords:
        search_keywords = [workflow_input.topic]

    for query in search_keywords[:3]:
        print(f"  Searching & scraping: '{query}'")
        results = search_and_scrape(query, limit=5, scrape_content=True)

        for r in results:
            normalized = r.url.rstrip("/").lower()
            if normalized == target_url or normalized in seen_urls:
                continue
            seen_urls.add(normalized)
            if r.content:
                all_competitors.append({
                    "url": r.url,
                    "title": r.title,
                    "query": query,
                    "content": r.content[:15000],
                })
        if len(all_competitors) >= 5:
            break

    print(f"  Found {len(all_competitors)} unique competitor pages with content.")

    if all_competitors:
        competitor_sections = []
        for i, comp in enumerate(all_competitors[:5], 1):
            competitor_sections.append(
                f"### Competitor {i}: {comp['title']}\n"
                f"URL: {comp['url']}\n"
                f"Ranking for: {comp['query']}\n\n"
                f"{comp['content']}"
            )
        competitor_content = "\n\n---\n\n".join(competitor_sections)
    else:
        competitor_content = "No competitor content was retrieved. Provide analysis based on general knowledge of the topic."

    # --- Step 5: Competitive freshness comparison ---
    print("[refresh_recommendations] Step 5/7: Running competitive freshness comparison...")
    competitive_prompt = load_prompt("refresh_competitive")
    competitive_rendered = render_prompt(
        competitive_prompt,
        {
            "topic": workflow_input.topic,
            "url": workflow_input.url or "Not provided",
            "sourceContent": source_content,
            "structuralAnalysis": json.dumps(structural_data, indent=2),
            "freshnessAudit": json.dumps(freshness_data, indent=2),
            "competitorContent": competitor_content,
        },
    )
    competitive_analysis = call_claude(
        system=competitive_rendered.system,
        user=competitive_rendered.user,
        model=competitive_rendered.config.model,
        temperature=competitive_rendered.config.temperature,
        max_tokens=competitive_rendered.config.max_tokens,
    )
    print("  Competitive freshness comparison complete.")

    # --- Step 6: Brand alignment check ---
    print("[refresh_recommendations] Step 6/7: Evaluating brand alignment...")
    artifacts = load_artifacts()
    artifact_bundle = build_artifact_bundle(artifacts)

    brand_prompt = load_prompt("refresh_brand")
    brand_rendered = render_prompt(
        brand_prompt,
        {
            "topic": workflow_input.topic,
            "url": workflow_input.url or "Not provided",
            "audience": workflow_input.audience or "Not specified",
            "sourceContent": source_content,
            "structuralAnalysis": json.dumps(structural_data, indent=2),
            "artifactBundle": artifact_bundle,
        },
    )
    brand_evaluation = call_claude(
        system=brand_rendered.system,
        user=brand_rendered.user,
        model=brand_rendered.config.model,
        temperature=brand_rendered.config.temperature,
        max_tokens=brand_rendered.config.max_tokens,
    )
    print("  Brand alignment check complete.")

    # --- Step 7: Synthesize recommendations ---
    print("[refresh_recommendations] Step 7/7: Synthesizing refresh recommendations...")
    synth_prompt = load_prompt("refresh_synthesize")
    synth_rendered = render_prompt(
        synth_prompt,
        {
            "topic": workflow_input.topic,
            "url": workflow_input.url or "Not provided",
            "audience": workflow_input.audience or "Not specified",
            "notes": workflow_input.notes or "None provided",
            "structuralAnalysis": json.dumps(structural_data, indent=2),
            "freshnessAudit": json.dumps(freshness_data, indent=2),
            "competitiveAnalysis": competitive_analysis,
            "brandEvaluation": brand_evaluation,
        },
    )
    final_recommendations = call_claude(
        system=synth_rendered.system,
        user=synth_rendered.user,
        model=synth_rendered.config.model,
        temperature=synth_rendered.config.temperature,
        max_tokens=synth_rendered.config.max_tokens,
    )
    print("  Synthesis complete.")

    # --- Step 8: Persist ---
    print("[refresh_recommendations] Saving output...")
    output = persist_workflow_run(
        workflow_name="refresh_recommendations",
        workflow_input=workflow_input,
        content=final_recommendations,
        json_data={
            "workflowType": "refresh-recommendations",
            "structural_analysis": structural_data,
            "freshness_audit": freshness_data,
            "competitors_analyzed": [
                {"url": c["url"], "title": c["title"], "query": c["query"]}
                for c in all_competitors
            ],
            "steps": {
                "competitive_analysis": competitive_analysis,
                "brand_evaluation": brand_evaluation,
            },
        },
    )

    print(f"[refresh_recommendations] Done. Output: {output.markdown_path}")
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
            'Example: echo \'{"topic": "Pricing Guide", "url": "https://example.com/pricing"}\' '
            "| python py/workflows/refresh_recommendations.py",
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
