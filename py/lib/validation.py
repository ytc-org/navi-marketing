"""Input/output validation models for content workflows."""

from __future__ import annotations

from pydantic import BaseModel, Field

from lib.gsc import GSCData


DEFAULT_TRACKING_PATH = "tracking/runs.md"


class WorkflowInput(BaseModel):
    """Common input accepted by every content workflow."""

    topic: str = Field(..., min_length=1, description="Short human-readable topic, page title, or working label")
    url: str | None = Field(None, description="Canonical page URL when available")
    source_path: str | None = Field(None, description="Path to a local Markdown or text source file")
    notes: str | None = Field(None, description="Extra operator notes or context")
    keywords: list[str] = Field(default_factory=list, description="Optional keyword or topic hints")
    audience: str | None = Field(None, description="Optional audience focus for this run")
    gsc: GSCData | None = Field(None, description="Optional Google Search Console data for this run. Skills populate this from the GSC MCP before calling the workflow. See py/lib/gsc.py for the shape and skills/_shared/fetch-gsc.md for guidance on what to fetch per workflow.")
    tracking_path: str = Field(DEFAULT_TRACKING_PATH, description="Markdown file to append a run log entry to")
    record_path: str | None = Field(None, description="Optional page/topic record file to append a run note to")
    output_slug: str | None = Field(None, description="Optional stable slug for output filenames")
    write_json_sidecar: bool = Field(True, description="Whether to write a JSON sidecar next to the Markdown output")

    # Workflow-specific options
    sitemap_url: str | None = Field(None, description="Override sitemap URL for internal_link_recommendations. Defaults to {domain}/sitemap.xml")
    write_article: bool = Field(False, description="If true on net_new_content_brief, also draft the full article from the brief using Opus")


class WorkflowOutput(BaseModel):
    """Standard result returned by every workflow."""

    workflow: str
    topic: str
    summary: str
    content: str
    markdown_path: str
    json_path: str | None = None
    tracking_path: str
