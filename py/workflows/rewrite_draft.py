#!/usr/bin/env python3
"""Rewrite Draft Workflow

Rewrites an existing page to improve alignment with brand voice, audience needs,
and search intent. Produces a complete rewritten draft with supporting analysis.

Steps:
  1. Fetch page content (Firecrawl or local file)
  2. Diagnose current content (Haiku) — identify strengths, weaknesses, tone, structure
  3. Search and scrape competitor pages for inspiration
  4. Build rewrite plan (Sonnet) — what to keep, cut, add, restructure, new sections
  5. Draft rewrite (Sonnet, high tokens) — produce the actual rewritten content
  6. Quality check (Sonnet) — verify against brand guardrails, keywords, accuracy
  7. Final assembly — combine plan, draft, and quality notes into output report

Usage (standalone):
  echo '{"topic": "Homepage", "url": "https://example.com"}' | python py/workflows/rewrite_draft.py

Usage (via server):
  POST http://localhost:8100/api/rewrite_draft
  Body: {"topic": "Homepage", "url": "https://example.com", "keywords": ["keyword1", "keyword2"]}
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
    """Execute the rewrite draft workflow. Called by the server or standalone."""

    log = WorkflowLogger("rewrite_draft", total_steps=8)
    log.start(workflow_input.topic)

    # --- Step 1: Get source content ---
    log.step("Fetching page content")
    source_content = read_source_file(workflow_input.source_path)
    if not source_content and workflow_input.url:
        source_content = scrape_page(workflow_input.url)
    if not source_content:
        raise ValueError("No source content available. Provide a URL or source_path.")
    log.detail(f"Got {len(source_content)} chars of content")
    log.step_done()

    # --- Step 2: Content diagnosis ---
    log.step("Diagnosing current content")
    diagnose_prompt = load_prompt("rewrite_diagnose")
    diagnose_rendered = render_prompt(
        diagnose_prompt,
        {
            "topic": workflow_input.topic,
            "url": workflow_input.url or "Not provided",
            "sourceContent": source_content,
        },
    )
    diagnosis_response = call_claude(
        system=diagnose_rendered.system,
        user=diagnose_rendered.user,
        model=diagnose_rendered.config.model,
        temperature=diagnose_rendered.config.temperature,
        max_tokens=diagnose_rendered.config.max_tokens,
    )
    diagnosis_data = _parse_json_response(diagnosis_response)
    log.step_done("Diagnosis complete")

    # --- Step 3: Search and scrape competitor pages ---
    log.step("Searching and scraping competitor pages")
    all_competitors: list[dict] = []
    seen_urls: set[str] = set()
    target_url = (workflow_input.url or "").rstrip("/").lower()

    # Use provided keywords, or extract from diagnosis
    search_queries = workflow_input.keywords or diagnosis_data.get("primary_topics", [])
    if not search_queries:
        search_queries = [workflow_input.topic]
    search_queries = search_queries[:3]

    for query in search_queries:
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
        competitor_content = "No competitor content was retrieved. Provide plan based on general best practices."

    # --- Step 4: Load artifacts ---
    log.step("Loading brand artifacts")
    artifacts = load_artifacts()
    artifact_bundle = build_artifact_bundle(artifacts)
    log.step_done("Artifacts loaded")

    # --- Step 5: Build rewrite plan ---
    log.step("Building rewrite plan")
    plan_prompt = load_prompt("rewrite_plan")
    plan_rendered = render_prompt(
        plan_prompt,
        {
            "topic": workflow_input.topic,
            "url": workflow_input.url or "Not provided",
            "audience": workflow_input.audience or "Not specified",
            "keywords": ", ".join(workflow_input.keywords) if workflow_input.keywords else "None provided",
            "notes": workflow_input.notes or "None provided",
            "diagnosis": json.dumps(diagnosis_data, indent=2),
            "competitorContent": competitor_content,
            "artifactBundle": artifact_bundle,
        },
    )
    rewrite_plan = call_claude(
        system=plan_rendered.system,
        user=plan_rendered.user,
        model=plan_rendered.config.model,
        temperature=plan_rendered.config.temperature,
        max_tokens=plan_rendered.config.max_tokens,
    )
    log.step_done("Rewrite plan complete")

    # --- Step 6: Draft the rewrite ---
    log.step("Writing rewrite draft")
    draft_prompt = load_prompt("rewrite_draft_content")
    draft_rendered = render_prompt(
        draft_prompt,
        {
            "topic": workflow_input.topic,
            "url": workflow_input.url or "Not provided",
            "audience": workflow_input.audience or "Not specified",
            "keywords": ", ".join(workflow_input.keywords) if workflow_input.keywords else "None provided",
            "voiceGuide": artifacts.get("writing-style", "No voice guide available"),
            "rewritePlan": rewrite_plan,
            "originalContent": source_content[:10000],
            "artifactBundle": artifact_bundle,
        },
    )
    draft_content = call_claude(
        system=draft_rendered.system,
        user=draft_rendered.user,
        model=draft_rendered.config.model,
        temperature=draft_rendered.config.temperature,
        max_tokens=draft_rendered.config.max_tokens,
    )
    log.step_done("Draft complete")

    # --- Step 7: Quality check ---
    log.step("Running quality check")
    quality_prompt = load_prompt("rewrite_quality")
    quality_rendered = render_prompt(
        quality_prompt,
        {
            "topic": workflow_input.topic,
            "keywords": ", ".join(workflow_input.keywords) if workflow_input.keywords else "None provided",
            "draft": draft_content,
            "guardrails": artifacts.get("brand-guardrails", "No guardrails available"),
        },
    )
    quality_response = call_claude(
        system=quality_rendered.system,
        user=quality_rendered.user,
        model=quality_rendered.config.model,
        temperature=quality_rendered.config.temperature,
        max_tokens=quality_rendered.config.max_tokens,
    )
    quality_data = _parse_json_response(quality_response)
    log.step_done("Quality check complete")

    # --- Step 8: Final assembly ---
    log.step("Assembling final output")
    final_report = _assemble_report(
        topic=workflow_input.topic,
        url=workflow_input.url,
        audience=workflow_input.audience,
        keywords=workflow_input.keywords,
        diagnosis=diagnosis_data,
        rewrite_plan=rewrite_plan,
        draft=draft_content,
        quality_notes=quality_data,
    )

    output = persist_workflow_run(
        workflow_name="rewrite_draft",
        workflow_input=workflow_input,
        content=final_report,
        json_data={
            "workflowType": "rewrite-draft",
            "diagnosis": diagnosis_data,
            "competitors_analyzed": [
                {"url": c["url"], "title": c["title"], "query": c["query"]}
                for c in all_competitors
            ],
            "quality_assessment": quality_data,
        },
    )

    log.step_done()
    log.done(output.markdown_path)
    return output


def _assemble_report(
    topic: str,
    url: str | None,
    audience: str | None,
    keywords: list[str] | None,
    diagnosis: dict,
    rewrite_plan: str,
    draft: str,
    quality_notes: dict,
) -> str:
    """Combine diagnosis, plan, draft, and quality notes into a single report."""

    sections = [
        f"# Rewrite Draft: {topic}",
        f"**URL:** {url or 'Not provided'}",
        f"**Target Audience:** {audience or 'Not specified'}",
        f"**Keywords:** {', '.join(keywords) if keywords else 'None provided'}",
        "",
    ]

    # Diagnosis summary
    if diagnosis:
        sections.append("## Content Diagnosis")
        if isinstance(diagnosis, dict):
            strengths = diagnosis.get("strengths", [])
            weaknesses = diagnosis.get("weaknesses", [])

            if strengths:
                sections.append("### What's Working")
                for item in strengths:
                    sections.append(f"- {item}")
                sections.append("")

            if weaknesses:
                sections.append("### Areas for Improvement")
                for item in weaknesses:
                    sections.append(f"- {item}")
                sections.append("")

    # Rewrite plan
    sections.append("## Rewrite Plan")
    sections.append(rewrite_plan)
    sections.append("")

    # Quality notes
    if quality_notes:
        sections.append("## Quality Assessment")
        if isinstance(quality_notes, dict):
            issues = quality_notes.get("issues", [])
            keyword_coverage = quality_notes.get("keyword_coverage", "Good")

            sections.append(f"**Keyword Coverage:** {keyword_coverage}")

            if issues:
                sections.append("### Items to Review")
                for issue in issues:
                    sections.append(f"- {issue}")
            sections.append("")

    # The draft itself
    sections.append("## Rewritten Draft")
    sections.append("")
    sections.append(draft)

    return "\n".join(sections)


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
            "| python py/workflows/rewrite_draft.py",
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
