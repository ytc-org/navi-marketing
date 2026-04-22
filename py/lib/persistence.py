"""Write workflow outputs to disk and append tracking records."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .validation import WorkflowInput, WorkflowOutput

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUTS_DIR = PROJECT_ROOT / "outputs"


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "run"


def timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")


def summarize(content: str, max_len: int = 220) -> str:
    return re.sub(r"\s+", " ", content).strip()[:max_len]


def _heading(slug: str) -> str:
    return slug.replace("_", " ").replace("-", " ").title()


def persist_workflow_run(
    *,
    workflow_name: str,
    workflow_input: WorkflowInput,
    content: str,
    json_data: dict | None = None,
) -> WorkflowOutput:
    """Write markdown output, optional JSON sidecar, and append tracking log."""

    slug = workflow_input.output_slug or slugify(workflow_input.topic)
    stamp = timestamp()
    generated_at = datetime.now(timezone.utc).isoformat()

    # --- Write markdown output ---
    output_dir = OUTPUTS_DIR / workflow_name
    output_dir.mkdir(parents=True, exist_ok=True)

    md_filename = f"{stamp}-{slug}.md"
    md_path = output_dir / md_filename
    md_relative = f"outputs/{workflow_name}/{md_filename}"

    md_content = "\n".join([
        f"# {_heading(workflow_name)}",
        "",
        f"- Generated At: {generated_at}",
        f"- Topic: {workflow_input.topic}",
        f"- URL: {workflow_input.url or 'n/a'}",
        f"- Source Path: {workflow_input.source_path or 'n/a'}",
        "",
        content.strip(),
        "",
    ])
    md_path.write_text(md_content, encoding="utf-8")

    # --- Write JSON sidecar ---
    json_relative: str | None = None
    if workflow_input.write_json_sidecar:
        json_filename = f"{stamp}-{slug}.json"
        json_path = output_dir / json_filename
        json_relative = f"outputs/{workflow_name}/{json_filename}"

        payload = {
            "workflow": workflow_name,
            "topic": workflow_input.topic,
            "url": workflow_input.url,
            "sourcePath": workflow_input.source_path,
            "keywords": workflow_input.keywords,
            "audience": workflow_input.audience,
            "generatedAt": generated_at,
            "content": content.strip(),
            **(json_data or {}),
        }
        json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    # --- Append tracking log ---
    tracking_path = PROJECT_ROOT / workflow_input.tracking_path
    tracking_path.parent.mkdir(parents=True, exist_ok=True)
    if not tracking_path.exists():
        tracking_path.write_text("# Run Log\n\n", encoding="utf-8")

    entry = "\n".join([
        f"## {generated_at} · {_heading(workflow_name)}",
        "",
        f"- Topic: {workflow_input.topic}",
        f"- URL: {workflow_input.url or 'n/a'}",
        f"- Output: {md_relative}",
        f"- JSON: {json_relative or 'disabled'}",
        f"- Summary: {summarize(content)}",
        "",
    ])
    with open(tracking_path, "a", encoding="utf-8") as f:
        f.write(entry + "\n")

    # --- Append optional record ---
    if workflow_input.record_path:
        record_path = PROJECT_ROOT / workflow_input.record_path
        record_path.parent.mkdir(parents=True, exist_ok=True)
        if not record_path.exists():
            record_path.write_text("# Record\n\n", encoding="utf-8")

        record_entry = "\n".join([
            f"## {generated_at} · {_heading(workflow_name)}",
            "",
            f"- Output: {md_relative}",
            f"- Summary: {summarize(content)}",
            "",
        ])
        with open(record_path, "a", encoding="utf-8") as f:
            f.write(record_entry + "\n")

    return WorkflowOutput(
        workflow=workflow_name,
        topic=workflow_input.topic,
        summary=summarize(content),
        content=content.strip(),
        markdown_path=md_relative,
        json_path=json_relative,
        tracking_path=workflow_input.tracking_path,
    )
