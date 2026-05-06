#!/usr/bin/env python3
"""Page Audit Workflow

Audits a page against brand context artifacts, real SERP competitor data,
and content structure. Produces a prioritized audit report with actionable
recommendations.

Steps:
  1. Fetch page content (Firecrawl or local file)
  2. Analyze content structure (headings, links, word count, etc.)
  3. Extract primary keywords from the page
  4. Search those keywords and scrape top-ranking competitor pages
  5. Evaluate against brand artifacts (style, audience, guardrails)
  6. Competitive gap analysis using real competitor content
  7. Synthesize into final audit report
  8. Persist output and tracking log

Usage (standalone):
  echo '{"topic": "Homepage", "url": "https://example.com"}' | python py/workflows/page_audit.py

Usage (via server):
  POST http://localhost:8100/api/page_audit
  Body: {"topic": "Homepage", "url": "https://example.com"}
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from lib.validation import WorkflowInput, WorkflowOutput
from lib.artifacts import load_artifacts, build_artifact_bundle, read_source_file
from lib.prompts import load_prompt, render_prompt
from lib.llm import call_claude
from lib.log import WorkflowLogger
from lib.scrape import scrape_page, search_and_scrape
from lib.persistence import persist_workflow_run
from lib.gsc import format_gsc_for_prompt


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
    """Execute the page audit workflow. Called by the server or standalone."""

    log = WorkflowLogger("page_audit", total_steps=8)
    log.start(workflow_input.topic)

    # --- Step 1: Get source content ---
    log.step("Fetching page content")
    source_content = read_source_file(workflow_input.source_path)
    if not source_content and workflow_input.url:
        source_content = scrape_page(workflow_input.url)
    if not source_content:
        raise ValueError("No source content available. Provide a URL or source_path.")
    log.detail(f"Got {len(source_content):,} chars of content")
    log.step_done()

    # --- Step 2: Structural analysis ---
    log.step("Analyzing content structure")
    analyze_prompt = load_prompt("page_audit_analyze")
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
    log.step_done("Structure analysis complete")

    # --- Step 3: Extract primary keywords ---
    log.step("Extracting primary keywords")
    kw_prompt = load_prompt("page_audit_extract_keywords")
    kw_rendered = render_prompt(
        kw_prompt,
        {
            "topic": workflow_input.topic,
            "url": workflow_input.url or "Not provided",
            "keywords": ", ".join(workflow_input.keywords)
            if workflow_input.keywords
            else "None provided",
            "sourceContent": source_content,
        },
    )
    kw_response = call_claude(
        system=kw_rendered.system,
        user=kw_rendered.user,
        model=kw_rendered.config.model,
        temperature=kw_rendered.config.temperature,
        max_tokens=kw_rendered.config.max_tokens,
    )
    keyword_data = _parse_json_response(kw_response)
    primary_keywords = keyword_data.get("primary_keywords", workflow_input.keywords or [])
    search_queries = keyword_data.get("search_queries", primary_keywords[:3])
    log.detail(f"Primary keywords: {', '.join(primary_keywords) if primary_keywords else '(none)'}")
    log.detail(f"Search queries: {', '.join(search_queries) if search_queries else '(none)'}")
    log.step_done()

    # --- Step 4: Search and scrape competitor pages ---
    log.step("Searching and scraping competitor pages")
    all_competitors: list[dict] = []
    seen_urls: set[str] = set()
    target_url = (workflow_input.url or "").rstrip("/").lower()

    # Use primary keywords first (broader = more results), then fall back to
    # LLM-generated search queries for long-tail coverage
    queries_to_search = primary_keywords[:3]
    if len(queries_to_search) < 2:
        queries_to_search.extend(search_queries[:2])
    # Deduplicate while preserving order
    queries_to_search = list(dict.fromkeys(queries_to_search))

    for query in queries_to_search:
        log.detail(f"Searching & scraping: '{query}'")
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
        if len(all_competitors) >= 8:
            break

    log.detail(f"Found {len(all_competitors)} unique competitor pages with content")
    log.step_done()

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
        competitor_content = "No competitor content was retrieved. Provide analysis based on general SEO knowledge."

    # --- Step 5: Brand evaluation ---
    log.step("Evaluating against brand artifacts")
    artifacts = load_artifacts()
    artifact_bundle = build_artifact_bundle(artifacts)

    eval_prompt = load_prompt("page_audit_evaluate")
    eval_rendered = render_prompt(
        eval_prompt,
        {
            "topic": workflow_input.topic,
            "url": workflow_input.url or "Not provided",
            "audience": workflow_input.audience or "Not specified",
            "keywords": ", ".join(primary_keywords) if primary_keywords else "None provided",
            "notes": workflow_input.notes or "None provided",
            "structuralAnalysis": structural_analysis,
            "artifactBundle": artifact_bundle,
            "sourceContent": source_content,
        },
    )
    evaluation_findings = call_claude(
        system=eval_rendered.system,
        user=eval_rendered.user,
        model=eval_rendered.config.model,
        temperature=eval_rendered.config.temperature,
        max_tokens=eval_rendered.config.max_tokens,
    )
    log.step_done("Brand evaluation complete")

    # --- Step 6: Competitive gap analysis ---
    log.step("Running competitive gap analysis")
    gap_prompt = load_prompt("page_audit_gaps")
    gap_rendered = render_prompt(
        gap_prompt,
        {
            "topic": workflow_input.topic,
            "url": workflow_input.url or "Not provided",
            "audience": workflow_input.audience or "Not specified",
            "keywords": ", ".join(primary_keywords) if primary_keywords else "None provided",
            "sourceContent": source_content,
            "structuralAnalysis": structural_analysis,
            "competitorContent": competitor_content,
        },
    )
    gap_analysis = call_claude(
        system=gap_rendered.system,
        user=gap_rendered.user,
        model=gap_rendered.config.model,
        temperature=gap_rendered.config.temperature,
        max_tokens=gap_rendered.config.max_tokens,
    )
    log.step_done("Gap analysis complete")

    # --- Step 7: Synthesize final report ---
    log.step("Synthesizing audit report")
    synth_prompt = load_prompt("page_audit_synthesize")
    synth_rendered = render_prompt(
        synth_prompt,
        {
            "topic": workflow_input.topic,
            "url": workflow_input.url or "Not provided",
            "audience": workflow_input.audience or "Not specified",
            "keywords": ", ".join(primary_keywords) if primary_keywords else "None provided",
            "notes": workflow_input.notes or "None provided",
            "evaluationFindings": evaluation_findings,
            "gapAnalysis": gap_analysis,
            "structuralAnalysis": structural_analysis,
            "gscSection": format_gsc_for_prompt(workflow_input.gsc),
        },
    )
    final_report = call_claude(
        system=synth_rendered.system,
        user=synth_rendered.user,
        model=synth_rendered.config.model,
        temperature=synth_rendered.config.temperature,
        max_tokens=synth_rendered.config.max_tokens,
    )
    log.step_done("Synthesis complete")

    # --- Step 8: Persist ---
    log.step("Saving output")
    output = persist_workflow_run(
        workflow_name="page_audit",
        workflow_input=workflow_input,
        content=final_report,
        json_data={
            "workflowType": "page-audit",
            "keywords_extracted": keyword_data,
            "competitors_analyzed": [
                {"url": c["url"], "title": c["title"], "query": c["query"]}
                for c in all_competitors
            ],
            "steps": {
                "structural_analysis": structural_analysis,
                "evaluation_findings": evaluation_findings,
                "gap_analysis": gap_analysis,
            },
        },
    )

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
            'Example: echo \'{"topic": "Homepage", "url": "https://example.com"}\' '
            "| python py/workflows/page_audit.py",
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
