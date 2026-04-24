#!/usr/bin/env python3
"""Internal Link Recommendations Workflow

Generates internal linking recommendations grounded in the brand's own sitemap
and ranked by semantic similarity. Two outputs:
  1. A prioritized recommendations report (markdown)
  2. A "_linked.md" version of the source article with the chosen links inserted inline

Pipeline:
  1. Fetch source page content (Firecrawl or local file)
  2. Fetch the brand's sitemap.xml and parse all URLs
  3. Extract topics & entities from the source page (Haiku)
  4. Embed topics + sitemap URL labels with OpenAI; rank candidates by cosine similarity
  5. Opus reviews ranked candidates and selects final links + placement (JSON plan)
  6. Sonnet inserts links into the article (separate _linked.md output)
  7. Sonnet synthesizes the final report (with rejection notes & gaps)
  8. Persist outputs and tracking log

Inputs:
  - topic: required — short page label
  - url: required — page URL (used both for scraping and to derive sitemap location)
  - source_path: optional — local file alternative to scraping
  - sitemap_url: optional — override default {domain}/sitemap.xml
  - keywords, audience, notes: optional context

Usage (via server):
  POST http://localhost:8100/api/internal_link_recommendations
  Body: {"topic": "Best Prepaid Plans", "url": "https://www.yournavi.com/posts/best-prepaid-unlimited-plans"}
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
from lib.scrape import scrape_page
from lib.persistence import persist_workflow_run, OUTPUTS_DIR, slugify, timestamp
from lib.sitemap import parse_sitemap, default_sitemap_url
from lib.embeddings import rank_urls_by_similarity


def _parse_json_response(text: str) -> dict:
    """Parse JSON from an LLM response, handling markdown code fences."""
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


def _format_ranked_candidates(ranked: list, target_url: str) -> str:
    """Format the embedding-ranked URL list as a Markdown bullet list for the prompt."""
    target_norm = target_url.rstrip("/").lower() if target_url else ""
    lines = []
    for i, r in enumerate(ranked, 1):
        if r.url.rstrip("/").lower() == target_norm:
            continue  # never recommend linking the page to itself
        lines.append(
            f"{i}. {r.url}\n"
            f"   label: \"{r.label}\"\n"
            f"   matched_topic: \"{r.matched_topic}\"\n"
            f"   similarity: {r.score:.3f}"
        )
    return "\n\n".join(lines) if lines else "No candidates found."


def run(workflow_input: WorkflowInput) -> WorkflowOutput:
    """Execute the internal link recommendations workflow."""

    log = WorkflowLogger("internal_link_recommendations", total_steps=8)
    log.start(workflow_input.topic)

    # --- Step 1: Source content ---
    log.step("Fetching page content")
    source_content = read_source_file(workflow_input.source_path)
    if not source_content and workflow_input.url:
        source_content = scrape_page(workflow_input.url)
    if not source_content:
        raise ValueError("No source content available. Provide a URL or source_path.")
    log.detail(f"Got {len(source_content)} chars of content")
    log.step_done()

    # --- Step 2: Sitemap ---
    log.step("Fetching and parsing sitemap")
    sitemap_url = workflow_input.sitemap_url
    if not sitemap_url:
        if not workflow_input.url:
            raise ValueError("sitemap_url is required when url is not provided.")
        sitemap_url = default_sitemap_url(workflow_input.url)
    log.detail(f"Sitemap: {sitemap_url}")
    try:
        sitemap_urls = parse_sitemap(sitemap_url)
    except Exception as exc:
        raise RuntimeError(
            f"Could not load sitemap at {sitemap_url}. "
            "Provide an explicit sitemap_url in the request, or verify the site exposes one."
        ) from exc
    log.detail(f"Parsed {len(sitemap_urls)} URLs from sitemap")
    log.step_done()

    # --- Step 3: Extract existing links + topics from page ---
    log.step("Extracting existing links and topics")
    extract_prompt = load_prompt("internal_links_extract")
    extract_rendered = render_prompt(
        extract_prompt,
        {
            "topic": workflow_input.topic,
            "url": workflow_input.url or "Not provided",
            "sourceContent": source_content,
        },
    )
    links_response = call_claude(
        system=extract_rendered.system,
        user=extract_rendered.user,
        model=extract_rendered.config.model,
        temperature=extract_rendered.config.temperature,
        max_tokens=extract_rendered.config.max_tokens,
    )
    links_data = _parse_json_response(links_response)

    topics_prompt = load_prompt("internal_links_topics")
    topics_rendered = render_prompt(
        topics_prompt,
        {
            "topic": workflow_input.topic,
            "url": workflow_input.url or "Not provided",
            "sourceContent": source_content,
        },
    )
    topics_response = call_claude(
        system=topics_rendered.system,
        user=topics_rendered.user,
        model=topics_rendered.config.model,
        temperature=topics_rendered.config.temperature,
        max_tokens=topics_rendered.config.max_tokens,
    )
    topics_data = _parse_json_response(topics_response)
    topic_phrases = topics_data.get("key_topics", [])
    entity_phrases = topics_data.get("entities", [])
    all_topic_phrases = list(dict.fromkeys(topic_phrases + entity_phrases))  # preserve order, dedupe
    log.detail(f"Found {len(links_data.get('internal_links', []))} existing links, "
               f"{len(all_topic_phrases)} topics/entities")
    log.step_done()

    if not all_topic_phrases:
        raise RuntimeError(
            "No topics extracted from the page — cannot rank sitemap URLs without query phrases."
        )

    # --- Step 4: Embed and rank ---
    log.step("Ranking sitemap URLs by semantic similarity")
    ranked = rank_urls_by_similarity(all_topic_phrases, sitemap_urls, top_n=30)
    ranked_text = _format_ranked_candidates(ranked, workflow_input.url or "")
    if ranked:
        log.detail(f"Top candidate score: {ranked[0].score:.3f} ({ranked[0].url})")
    else:
        log.detail("No candidates ranked")
    log.step_done()

    # --- Step 5: Opus selects links ---
    log.step("Opus selecting and placing links")
    artifacts = load_artifacts()
    artifact_bundle = build_artifact_bundle(artifacts)
    gen_prompt = load_prompt("internal_links_generate")
    gen_rendered = render_prompt(
        gen_prompt,
        {
            "topic": workflow_input.topic,
            "url": workflow_input.url or "Not provided",
            "sourceContent": source_content,
            "existingLinks": json.dumps(links_data, indent=2),
            "keyTopics": json.dumps(topics_data, indent=2),
            "rankedCandidates": ranked_text,
            "artifactBundle": artifact_bundle,
        },
    )
    plan_response = call_claude(
        system=gen_rendered.system,
        user=gen_rendered.user,
        model=gen_rendered.config.model,
        temperature=gen_rendered.config.temperature,
        max_tokens=gen_rendered.config.max_tokens,
    )
    link_plan = _parse_json_response(plan_response)
    selected = link_plan.get("selected_links", [])
    rejected = link_plan.get("rejected_candidates", [])
    log.detail(f"Selected {len(selected)} links, rejected {len(rejected)} candidates")
    log.step_done()

    # --- Step 6: Sonnet inserts links into the article ---
    log.step("Inserting links into the article")
    if selected:
        insert_prompt = load_prompt("internal_links_insert")
        insert_rendered = render_prompt(
            insert_prompt,
            {
                "sourceContent": source_content,
                "linkPlan": json.dumps(selected, indent=2),
            },
        )
        linked_article = call_claude(
            system=insert_rendered.system,
            user=insert_rendered.user,
            model=insert_rendered.config.model,
            temperature=insert_rendered.config.temperature,
            max_tokens=insert_rendered.config.max_tokens,
        )
    else:
        linked_article = source_content  # nothing to insert
    log.detail(f"Linked article: {len(linked_article)} chars")
    log.step_done()

    # --- Step 7: Synthesize report ---
    log.step("Synthesizing recommendations report")
    synth_prompt = load_prompt("internal_links_synthesize")
    synth_rendered = render_prompt(
        synth_prompt,
        {
            "topic": workflow_input.topic,
            "url": workflow_input.url or "Not provided",
            "existingLinks": json.dumps(links_data, indent=2),
            "keyTopics": json.dumps(topics_data, indent=2),
            "rankedCandidates": ranked_text,
            "linkPlan": json.dumps(link_plan, indent=2),
        },
    )
    final_report = call_claude(
        system=synth_rendered.system,
        user=synth_rendered.user,
        model=synth_rendered.config.model,
        temperature=synth_rendered.config.temperature,
        max_tokens=synth_rendered.config.max_tokens,
    )

    log.step_done()

    # --- Persist ---
    log.step("Saving outputs")
    output = persist_workflow_run(
        workflow_name="internal_link_recommendations",
        workflow_input=workflow_input,
        content=final_report,
        json_data={
            "workflowType": "internal-link-recommendations",
            "sitemap_url": sitemap_url,
            "sitemap_url_count": len(sitemap_urls),
            "topics_used_for_ranking": all_topic_phrases,
            "top_candidates": [
                {"url": r.url, "label": r.label, "score": round(r.score, 4), "matched_topic": r.matched_topic}
                for r in ranked
            ],
            "link_plan": link_plan,
            "existing_links": links_data,
        },
    )

    # Write the linked-article companion file alongside the main report
    slug = workflow_input.output_slug or slugify(workflow_input.topic)
    stamp = timestamp()
    linked_dir = OUTPUTS_DIR / "internal_link_recommendations"
    linked_dir.mkdir(parents=True, exist_ok=True)
    linked_path = linked_dir / f"{stamp}-{slug}-linked.md"
    linked_header = "\n".join([
        f"# Linked version: {workflow_input.topic}",
        "",
        f"Source URL: {workflow_input.url or 'n/a'}",
        f"Generated: {stamp}",
        f"Links inserted: {len(selected)}",
        "",
        "---",
        "",
    ])
    linked_path.write_text(linked_header + linked_article.strip() + "\n", encoding="utf-8")
    log.detail(f"Linked article saved to {linked_path.relative_to(linked_dir.parent.parent)}")
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
