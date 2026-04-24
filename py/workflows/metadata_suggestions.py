#!/usr/bin/env python3
"""Metadata Suggestions Workflow

Generates optimized title tags, meta descriptions, heading structure, and on-page
SEO guidance. Multi-step process:

  1. Fetch page content (Firecrawl or local file)
  2. Extract current metadata (title, description, headings, schema, OG tags)
  3. Analyze page keywords and placement
  4. Search for primary keywords, capture competitor SERP metadata
  5. Generate 3 title options, 3 description options, optimized headings
  6. Synthesize final recommendations with character counts and rationale

Usage (standalone):
  echo '{"topic": "Homepage", "url": "https://example.com"}' | python py/workflows/metadata_suggestions.py

Usage (via server):
  POST http://localhost:8100/api/metadata_suggestions
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
from lib.scrape import scrape_page, search
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
    """Execute the metadata suggestions workflow. Called by the server or standalone."""

    log = WorkflowLogger("metadata_suggestions", total_steps=7)
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

    # --- Step 2: Extract current metadata ---
    log.step("Extracting current metadata")
    extract_prompt = load_prompt("metadata_extract")
    extract_rendered = render_prompt(
        extract_prompt,
        {
            "topic": workflow_input.topic,
            "url": workflow_input.url or "Not provided",
            "sourceContent": source_content,
        },
    )
    extract_response = call_claude(
        system=extract_rendered.system,
        user=extract_rendered.user,
        model=extract_rendered.config.model,
        temperature=extract_rendered.config.temperature,
        max_tokens=extract_rendered.config.max_tokens,
    )
    current_metadata = _parse_json_response(extract_response)
    log.step_done("Current metadata extracted")

    # --- Step 3: Keyword analysis ---
    log.step("Analyzing keywords and placement")
    kw_prompt = load_prompt("metadata_keywords")
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
    keyword_analysis = _parse_json_response(kw_response)
    primary_keywords = keyword_analysis.get("primary_keywords", workflow_input.keywords or [])
    log.detail(f"Primary keywords identified: {primary_keywords}")
    log.step_done()

    # --- Step 4: Search SERP landscape for competitor metadata ---
    log.step("Searching SERP landscape")
    serp_data: list[dict] = []

    # Search using primary keywords (use first 2-3 for SERP metadata)
    search_queries = primary_keywords[:3]
    if not search_queries and workflow_input.keywords:
        search_queries = workflow_input.keywords[:2]
    if not search_queries:
        search_queries = [workflow_input.topic]

    for query in search_queries[:2]:  # Search only top 2 queries to save cost
        log.detail(f"Searching: '{query}'")
        results = search(query, limit=10)
        for r in results:
            if r.url and r.title:  # Only keep results with metadata
                serp_data.append({
                    "query": query,
                    "url": r.url,
                    "title": r.title,
                    "description": r.description,
                })
        if len(serp_data) >= 15:
            break

    log.detail(f"Found {len(serp_data)} SERP results with metadata")
    log.step_done()

    # Format SERP data for prompt
    serp_content = ""
    if serp_data:
        serp_sections = []
        for i, item in enumerate(serp_data[:15], 1):
            serp_sections.append(
                f"### Result {i}\n"
                f"Query: {item['query']}\n"
                f"Title: {item['title']}\n"
                f"Description: {item['description']}\n"
            )
        serp_content = "\n".join(serp_sections)
    else:
        serp_content = "No SERP data available. Generate recommendations based on general SEO best practices."

    # --- Step 5: Generate metadata options ---
    log.step("Generating metadata options")
    gen_prompt = load_prompt("metadata_generate")
    gen_rendered = render_prompt(
        gen_prompt,
        {
            "topic": workflow_input.topic,
            "url": workflow_input.url or "Not provided",
            "keywords": ", ".join(primary_keywords) if primary_keywords else "None identified",
            "currentMetadata": json.dumps(current_metadata, indent=2),
            "keywordAnalysis": json.dumps(keyword_analysis, indent=2),
            "serpData": serp_content,
        },
    )
    gen_response = call_claude(
        system=gen_rendered.system,
        user=gen_rendered.user,
        model=gen_rendered.config.model,
        temperature=gen_rendered.config.temperature,
        max_tokens=gen_rendered.config.max_tokens,
    )
    log.step_done("Metadata options generated")

    # --- Step 6: Synthesize final recommendations ---
    log.step("Synthesizing recommendations")
    artifacts = load_artifacts()
    artifact_bundle = build_artifact_bundle(artifacts)

    synth_prompt = load_prompt("metadata_synthesize")
    synth_rendered = render_prompt(
        synth_prompt,
        {
            "topic": workflow_input.topic,
            "url": workflow_input.url or "Not provided",
            "audience": workflow_input.audience or "Not specified",
            "keywords": ", ".join(primary_keywords) if primary_keywords else "None identified",
            "notes": workflow_input.notes or "None provided",
            "currentDate": __import__("datetime").date.today().isoformat(),
            "currentMetadata": json.dumps(current_metadata, indent=2),
            "keywordAnalysis": json.dumps(keyword_analysis, indent=2),
            "generatedOptions": gen_response,
            "artifactBundle": artifact_bundle,
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

    # --- Step 7: Persist ---
    log.step("Saving output")
    output = persist_workflow_run(
        workflow_name="metadata_suggestions",
        workflow_input=workflow_input,
        content=final_report,
        json_data={
            "workflowType": "metadata-suggestions",
            "current_metadata": current_metadata,
            "keyword_analysis": keyword_analysis,
            "serp_results_count": len(serp_data),
            "primary_keywords": primary_keywords,
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
            "| python py/workflows/metadata_suggestions.py",
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
