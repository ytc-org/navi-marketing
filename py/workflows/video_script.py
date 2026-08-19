#!/usr/bin/env python3
"""Video Script Workflow

Generates 2-3 short-form video script variations (with distinct angles/hooks)
from a source article, local draft, or written brief, in the voice of either
the Navi or Save On Wireless brand. Voice rules come from the brand's video
style guide artifact, distilled from the team's produced-script corpus.

Steps:
  1. Get source content (URL scrape, local file, or notes-as-brief)
  2. Load artifacts (brand bundle + the brand's video style guide)
  3. Distill source (Haiku) — facts, numbers, catches, candidate angles
  4. Pick angles (Sonnet) — N distinct angles mapped to style-guide hook patterns
  5. Write scripts (Opus) — N full voiceover scripts with beat labels
  6. Compliance review (Sonnet) — brand/guardrail check, human-review flags
  7. Final assembly — angles, scripts, and review notes into one report

Usage (standalone):
  echo '{"topic": "TCO explainer", "url": "https://...", "brand": "save-on-wireless"}' \
    | python py/workflows/video_script.py

Usage (via server):
  POST http://localhost:8100/api/video_script
  Body: {"topic": "...", "url": "...", "brand": "navi", "script_count": 3}
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from lib.validation import WorkflowInput, WorkflowOutput
from lib.artifacts import (
    load_artifacts,
    build_artifact_bundle,
    read_source_file,
    recommendation_guardrails_block,
    normalize_brand,
    video_style_block,
    VIDEO_STYLE_ARTIFACTS,
)
from lib.prompts import load_prompt, render_prompt
from lib.llm import call_claude
from lib.log import WorkflowLogger
from lib.scrape import scrape_page
from lib.persistence import persist_workflow_run
from lib.gsc import format_gsc_for_prompt


BRAND_DISPLAY_NAMES = {
    "navi": "Navi",
    "save-on-wireless": "Save On Wireless",
}


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
    """Execute the video script workflow. Called by the server or standalone."""

    log = WorkflowLogger("video_script", total_steps=7)
    log.start(workflow_input.topic)

    brand = normalize_brand(workflow_input.brand)
    brand_name = BRAND_DISPLAY_NAMES[brand]
    script_count = workflow_input.script_count

    # --- Step 1: Get source content ---
    log.step("Getting source content")
    source_content = read_source_file(workflow_input.source_path)
    if not source_content and workflow_input.url:
        source_content = scrape_page(workflow_input.url)
    if not source_content and workflow_input.notes:
        # A written brief in `notes` is a valid source for video scripts.
        source_content = workflow_input.notes
    if not source_content:
        raise ValueError(
            "No source content available. Provide a URL, source_path, or a brief in notes."
        )
    log.detail(f"Got {len(source_content)} chars of source material ({brand_name})")
    log.step_done()

    # --- Step 2: Load artifacts ---
    log.step("Loading brand artifacts")
    artifacts = load_artifacts()
    style_guide = video_style_block(artifacts, brand)
    if not artifacts.get(VIDEO_STYLE_ARTIFACTS[brand]):
        log.warn(
            f"artifacts/{VIDEO_STYLE_ARTIFACTS[brand]}.md is missing — "
            "scripts will run without the brand's video voice contract"
        )
    guardrails = recommendation_guardrails_block(artifacts)
    if brand == "navi":
        # The six standard artifacts are Navi's; they don't apply to Save On Wireless.
        artifact_bundle = build_artifact_bundle(
            artifacts,
            include=[
                "company-context",
                "audience-personas",
                "brand-guardrails",
                "products-and-services",
                "plans-and-pricing",
            ],
        )
        brand_guardrails = artifacts.get("brand-guardrails") or "No brand guardrails on file."
    else:
        artifact_bundle = (
            "No separate brand-context artifacts exist for Save On Wireless. "
            "The video style guide above is the authoritative brand context."
        )
        brand_guardrails = (
            "Use the Do/Don't list and claims rules in the video style guide as the guardrails."
        )
    log.step_done("Artifacts loaded")

    # --- Step 3: Distill source material ---
    log.step("Distilling source material")
    source_prompt = load_prompt("video_script_source")
    source_rendered = render_prompt(
        source_prompt,
        {
            "topic": workflow_input.topic,
            "audience": workflow_input.audience or "General consumers",
            "keywords": ", ".join(workflow_input.keywords) if workflow_input.keywords else "None provided",
            "notes": workflow_input.notes or "None provided",
            "sourceContent": source_content[:20000],
        },
    )
    source_summary = call_claude(
        system=source_rendered.system,
        user=source_rendered.user,
        model=source_rendered.config.model,
        temperature=source_rendered.config.temperature,
        max_tokens=source_rendered.config.max_tokens,
    )
    log.step_done("Distillation complete")

    # --- Step 4: Pick angles ---
    log.step(f"Choosing {script_count} angles")
    angles_prompt = load_prompt("video_script_angles")
    angles_rendered = render_prompt(
        angles_prompt,
        {
            "topic": workflow_input.topic,
            "audience": workflow_input.audience or "General consumers",
            "notes": workflow_input.notes or "None provided",
            "brandName": brand_name,
            "videoStyleGuide": style_guide,
            "scriptCount": str(script_count),
            "sourceSummary": source_summary,
        },
    )
    angles_response = call_claude(
        system=angles_rendered.system,
        user=angles_rendered.user,
        model=angles_rendered.config.model,
        temperature=angles_rendered.config.temperature,
        max_tokens=angles_rendered.config.max_tokens,
    )
    angles_data = _parse_json_response(angles_response)
    angles = angles_data.get("angles", [])
    if angles:
        log.detail(f"Angles: {', '.join(a.get('title', '?') for a in angles)}")
    else:
        log.warn("Angle selection returned no parseable JSON — passing raw text to the writer")
    log.step_done()

    # --- Step 5: Write the scripts ---
    log.step("Writing scripts")
    generate_prompt = load_prompt("video_script_generate")
    generate_rendered = render_prompt(
        generate_prompt,
        {
            "topic": workflow_input.topic,
            "audience": workflow_input.audience or "General consumers",
            "notes": workflow_input.notes or "None provided",
            "brandName": brand_name,
            "videoStyleGuide": style_guide,
            "artifactBundle": artifact_bundle,
            "recommendationGuardrails": guardrails,
            "scriptCount": str(script_count),
            "sourceSummary": source_summary,
            "angles": json.dumps(angles, indent=2) if angles else angles_response,
            "gscSection": format_gsc_for_prompt(workflow_input.gsc),
        },
    )
    scripts = call_claude(
        system=generate_rendered.system,
        user=generate_rendered.user,
        model=generate_rendered.config.model,
        temperature=generate_rendered.config.temperature,
        max_tokens=generate_rendered.config.max_tokens,
    )
    log.step_done("Scripts written")

    # --- Step 6: Compliance review ---
    log.step("Reviewing scripts against brand guardrails")
    review_prompt = load_prompt("video_script_review")
    review_rendered = render_prompt(
        review_prompt,
        {
            "topic": workflow_input.topic,
            "brandName": brand_name,
            "videoStyleGuide": style_guide,
            "brandGuardrails": brand_guardrails,
            "recommendationGuardrails": guardrails,
            "sourceSummary": source_summary,
            "scripts": scripts,
        },
    )
    review_response = call_claude(
        system=review_rendered.system,
        user=review_rendered.user,
        model=review_rendered.config.model,
        temperature=review_rendered.config.temperature,
        max_tokens=review_rendered.config.max_tokens,
    )
    review_data = _parse_json_response(review_response)
    log.step_done("Review complete")

    # --- Step 7: Final assembly ---
    log.step("Assembling final output")
    final_report = _assemble_report(
        topic=workflow_input.topic,
        brand_name=brand_name,
        url=workflow_input.url,
        audience=workflow_input.audience,
        angles=angles,
        scripts=scripts,
        review=review_data,
    )

    output = persist_workflow_run(
        workflow_name="video_script",
        workflow_input=workflow_input,
        content=final_report,
        json_data={
            "workflowType": "video-script",
            "brand": brand,
            "scriptCount": script_count,
            "steps": {
                "source_summary": source_summary,
                "angles": angles_data,
                "review": review_data,
            },
        },
    )

    log.step_done()
    log.done(output.markdown_path)
    return output


def _assemble_report(
    topic: str,
    brand_name: str,
    url: str | None,
    audience: str | None,
    angles: list[dict],
    scripts: str,
    review: dict,
) -> str:
    """Combine angles, scripts, and review notes into a single report."""

    sections = [
        f"# Video Scripts: {topic}",
        f"**Brand:** {brand_name}",
        f"**Source URL:** {url or 'Not provided'}",
        f"**Target Audience:** {audience or 'General consumers'}",
        "",
    ]

    if angles:
        sections.append("## Angles")
        for i, angle in enumerate(angles, 1):
            sections.append(
                f"{i}. **{angle.get('title', 'Untitled')}** "
                f"({angle.get('hook_pattern', 'hook pattern n/a')}) — "
                f"{angle.get('rationale', '')}"
            )
        sections.append("")

    review_scripts = review.get("scripts", []) if isinstance(review, dict) else []
    if review_scripts or review.get("overall_notes"):
        sections.append("## Compliance Review")
        if review.get("overall_notes"):
            sections.append(review["overall_notes"])
            sections.append("")
        for entry in review_scripts:
            verdict = entry.get("verdict", "?")
            sections.append(f"### Script {entry.get('script', '?')} — {verdict}")
            for issue in entry.get("issues", []):
                sections.append(f"- Issue: {issue}")
            for item in entry.get("human_review", []):
                sections.append(f"- Human review: {item}")
            sections.append("")

    sections.append("## Scripts")
    sections.append("")
    sections.append(scripts)

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
            'Example: echo \'{"topic": "TCO explainer", "url": "https://example.com", '
            '"brand": "save-on-wireless"}\' | python py/workflows/video_script.py',
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
