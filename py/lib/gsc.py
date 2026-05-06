"""Google Search Console data shapes and prompt formatting.

Workflows accept GSC data via WorkflowInput.gsc (a structured GSCData object).
Skills are responsible for fetching from the GSC MCP and populating this field.

The format_gsc_for_prompt() helper renders any non-empty GSCData into a
prompt-ready Markdown block. Workflows pass the rendered block to the LLM
under the {{ gscSection }} variable. When no GSC data is provided, the
helper returns an empty string and the section disappears from the prompt.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class GSCMetrics(BaseModel):
    """Aggregate metrics for a single property/page over a window."""

    clicks: int = 0
    impressions: int = 0
    ctr: float = 0.0  # 0.0–1.0
    position: float = 0.0


class GSCQueryRow(BaseModel):
    """One row from a query-dimension search analytics call."""

    query: str
    clicks: int = 0
    impressions: int = 0
    ctr: float = 0.0  # 0.0–1.0
    position: float = 0.0


class GSCPageRow(BaseModel):
    """One row from a page-dimension search analytics call."""

    page: str
    clicks: int = 0
    impressions: int = 0
    ctr: float = 0.0  # 0.0–1.0
    position: float = 0.0


class GSCComparison(BaseModel):
    """Two-period comparison (e.g., last 90d vs prior 90d) for trend analysis."""

    period_label: str = ""  # e.g., "last 90d vs prior 90d"
    current: GSCMetrics
    prior: GSCMetrics


class GSCData(BaseModel):
    """Google Search Console data attached to a workflow run.

    All fields optional — pass only what's relevant. Per-workflow guidance
    lives in skills/_shared/fetch-gsc.md and each workflow's SKILL.md.
    """

    property_url: str | None = None
    date_range: str | None = None  # human-readable, e.g., "last 28 days (2026-04-08 to 2026-05-06)"
    page_url: str | None = None  # the specific page these metrics describe (if filtered)
    page_totals: GSCMetrics | None = None
    comparison: GSCComparison | None = None  # period-over-period totals
    top_queries: list[GSCQueryRow] = Field(default_factory=list)
    top_pages: list[GSCPageRow] = Field(default_factory=list)
    notes: str | None = None  # free-form analyst commentary


# ─── Formatting ──────────────────────────────────────────────────────────────


def _fmt_int(n: int) -> str:
    return f"{n:,}"


def _fmt_pct(x: float) -> str:
    """Render a 0.0–1.0 ratio as a percentage with one decimal."""
    return f"{x * 100:.1f}%"


def _fmt_pos(x: float) -> str:
    return f"{x:.1f}"


def _delta_pct(current: float, prior: float) -> str:
    """Human delta as a signed percentage. Returns 'n/a' if prior is 0."""
    if prior == 0:
        return "n/a"
    pct = (current - prior) / prior * 100
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.1f}%"


def _delta_pos(current: float, prior: float) -> str:
    """Position delta. LOWER position is better. Returns signed delta with directional verb."""
    if prior == 0:
        return "n/a"
    diff = current - prior
    if abs(diff) < 0.05:
        return "≈0 (flat)"
    if diff < 0:
        return f"improved {abs(diff):.1f}"
    return f"worsened {diff:.1f}"


def format_gsc_for_prompt(gsc: GSCData | None) -> str:
    """Render a GSCData object into a Markdown block for prompt injection.

    Returns "" when gsc is None or has no usable content. Workflows that thread
    {{ gscSection }} into their prompts will simply have an empty section.
    """
    if gsc is None:
        return ""

    # If literally nothing is set, return empty
    has_anything = any([
        gsc.page_totals is not None,
        gsc.comparison is not None,
        bool(gsc.top_queries),
        bool(gsc.top_pages),
        bool(gsc.notes),
    ])
    if not has_anything:
        return ""

    parts: list[str] = ["## Google Search Console performance", ""]

    # Header metadata
    meta_lines: list[str] = []
    if gsc.property_url:
        meta_lines.append(f"**Property:** {gsc.property_url}")
    if gsc.date_range:
        meta_lines.append(f"**Date range:** {gsc.date_range}")
    if gsc.page_url:
        meta_lines.append(f"**Page filter:** {gsc.page_url}")
    if meta_lines:
        parts.extend(meta_lines)
        parts.append("")

    # Page totals
    if gsc.page_totals is not None:
        t = gsc.page_totals
        parts.append("### Totals")
        parts.append(f"- Clicks: {_fmt_int(t.clicks)}")
        parts.append(f"- Impressions: {_fmt_int(t.impressions)}")
        parts.append(f"- CTR: {_fmt_pct(t.ctr)}")
        parts.append(f"- Avg position: {_fmt_pos(t.position)}")
        parts.append("")

    # Comparison
    if gsc.comparison is not None:
        c, p = gsc.comparison.current, gsc.comparison.prior
        label = gsc.comparison.period_label or "current vs prior"
        parts.append(f"### Comparison ({label})")
        parts.append("| Metric | Current | Prior | Δ |")
        parts.append("|---|---:|---:|---:|")
        parts.append(
            f"| Clicks | {_fmt_int(c.clicks)} | {_fmt_int(p.clicks)} | "
            f"{_delta_pct(c.clicks, p.clicks)} |"
        )
        parts.append(
            f"| Impressions | {_fmt_int(c.impressions)} | {_fmt_int(p.impressions)} | "
            f"{_delta_pct(c.impressions, p.impressions)} |"
        )
        parts.append(
            f"| CTR | {_fmt_pct(c.ctr)} | {_fmt_pct(p.ctr)} | "
            f"{_delta_pct(c.ctr, p.ctr)} |"
        )
        parts.append(
            f"| Position | {_fmt_pos(c.position)} | {_fmt_pos(p.position)} | "
            f"{_delta_pos(c.position, p.position)} |"
        )
        parts.append("")

    # Top queries
    if gsc.top_queries:
        parts.append("### Top queries")
        parts.append("| Query | Clicks | Impressions | CTR | Position |")
        parts.append("|---|---:|---:|---:|---:|")
        for row in gsc.top_queries:
            # Escape pipe characters in queries to avoid breaking the table
            safe_query = row.query.replace("|", "\\|")
            parts.append(
                f"| {safe_query} | {_fmt_int(row.clicks)} | {_fmt_int(row.impressions)} | "
                f"{_fmt_pct(row.ctr)} | {_fmt_pos(row.position)} |"
            )
        parts.append("")

    # Top pages
    if gsc.top_pages:
        parts.append("### Top pages")
        parts.append("| Page | Clicks | Impressions | CTR | Position |")
        parts.append("|---|---:|---:|---:|---:|")
        for row in gsc.top_pages:
            parts.append(
                f"| {row.page} | {_fmt_int(row.clicks)} | {_fmt_int(row.impressions)} | "
                f"{_fmt_pct(row.ctr)} | {_fmt_pos(row.position)} |"
            )
        parts.append("")

    # Analyst notes
    if gsc.notes:
        parts.append("### Analyst notes")
        parts.append(gsc.notes.strip())
        parts.append("")

    return "\n".join(parts).rstrip() + "\n"
