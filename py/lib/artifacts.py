"""Load and bundle Markdown artifact files from the artifacts/ directory."""

from __future__ import annotations

from pathlib import Path

# Project root is two levels up from this file (py/lib/ -> repo root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

ARTIFACT_DIR = PROJECT_ROOT / "artifacts"

KNOWN_ARTIFACTS = [
    "workflow-context",
    "company-context",
    "writing-style",
    "audience-personas",
    "brand-guardrails",
    "products-and-services",
    # Optional, maintained-by-hand artifacts. Absent on most setups; when
    # present they flow into the relevant prompts automatically.
    "plans-and-pricing",
    "recommendation-guardrails",
    # Video style guides, distilled from the team's example script corpus.
    # Injected only by the video_script workflow (never in the default bundle).
    "video-style-guide",
    "video-style-guide-save-on-wireless",
]


def _heading(slug: str) -> str:
    return slug.replace("-", " ").replace("_", " ").title()


def load_artifacts(artifact_dir: Path | None = None) -> dict[str, str]:
    """Read every .md file in the artifacts directory into a dict keyed by stem."""
    artifact_dir = artifact_dir or ARTIFACT_DIR
    artifacts: dict[str, str] = {}
    if not artifact_dir.is_dir():
        return artifacts
    for path in sorted(artifact_dir.glob("*.md")):
        artifacts[path.stem] = path.read_text(encoding="utf-8")
    return artifacts


# Artifacts that carry no brand context the model needs in a prompt.
#   - workflow-context: operating instructions for the ops system itself.
#   - recommendation-guardrails: a suppression list injected separately into
#     evaluation/synthesis prompts (not part of the brand context bundle).
#   - video-style-guide*: video-only voice guides injected separately by the
#     video_script workflow (article workflows must not absorb video style).
_DEFAULT_EXCLUDED = {
    "workflow-context",
    "recommendation-guardrails",
    "video-style-guide",
    "video-style-guide-save-on-wireless",
}

# Default selection: every known artifact except the excluded ones above.
DEFAULT_ARTIFACTS = [n for n in KNOWN_ARTIFACTS if n not in _DEFAULT_EXCLUDED]


def recommendation_guardrails_block(artifacts: dict[str, str]) -> str:
    """Return the team's recommendation-suppression list as a prompt block.

    This is the "stop telling me X" feedback loop: when a kind of finding keeps
    being unhelpful, the team (or Claude, on request) appends a rule to
    ``artifacts/recommendation-guardrails.md`` and it gets injected here so
    future runs honor it. Returns a neutral placeholder when the artifact is
    absent so prompts can render unconditionally.
    """
    content = (artifacts.get("recommendation-guardrails") or "").strip()
    if not content:
        return "No recommendation guardrails on file."
    return content


# Brands the video_script workflow can target, mapped to their style guide
# artifact. Keys are normalized brand slugs (see normalize_brand).
VIDEO_STYLE_ARTIFACTS = {
    "navi": "video-style-guide",
    "save-on-wireless": "video-style-guide-save-on-wireless",
}


def normalize_brand(brand: str | None) -> str:
    """Normalize a brand input to a known slug. Raises ValueError on unknown brands.

    Defaults to "navi" when omitted. Accepts loose spellings like
    "Save On Wireless" or "save_on_wireless".
    """
    slug = (brand or "navi").strip().lower().replace("_", "-").replace(" ", "-")
    aliases = {"sow": "save-on-wireless", "saveonwireless": "save-on-wireless"}
    slug = aliases.get(slug, slug)
    if slug not in VIDEO_STYLE_ARTIFACTS:
        known = ", ".join(sorted(VIDEO_STYLE_ARTIFACTS))
        raise ValueError(f"Unknown brand '{brand}'. Known brands: {known}")
    return slug


def video_style_block(artifacts: dict[str, str], brand: str | None = None) -> str:
    """Return the brand's video style guide as a prompt block.

    Returns a neutral placeholder when the guide artifact is absent so prompts
    can render unconditionally — but workflows should warn the user, since the
    guide is what keeps scripts on-brand.
    """
    slug = VIDEO_STYLE_ARTIFACTS[normalize_brand(brand)]
    content = (artifacts.get(slug) or "").strip()
    if not content:
        return (
            "No video style guide on file for this brand. Fall back to the brand "
            "guardrails and writing style context, keep scripts in a short-form "
            "spoken-voiceover format, and flag the output for human style review."
        )
    return content


def build_artifact_bundle(
    artifacts: dict[str, str],
    include: list[str] | None = None,
) -> str:
    """Format selected artifacts into a single Markdown string for prompt injection.

    `include` is an allowlist of artifact stems (e.g. ["writing-style",
    "brand-guardrails"]) — pass only what a given prompt actually needs to keep
    token usage down. When omitted, defaults to every known artifact except
    `workflow-context`.

    Only known artifacts are emitted, in their canonical order; stray files in
    artifacts/ (e.g. README.md) are never bundled.
    """
    selected = set(include) if include is not None else set(DEFAULT_ARTIFACTS)

    sections: list[str] = []
    for name in KNOWN_ARTIFACTS:
        if name not in selected:
            continue
        content = artifacts.get(name)
        if content:
            sections.append(f"## {_heading(name)}\n{content.strip()}")

    return "\n\n".join(sections) if sections else "No artifact files were found in artifacts/."


def read_source_file(source_path: str | None) -> str | None:
    """Try to read a local file relative to the project root. Returns None on failure."""
    if not source_path:
        return None
    path = PROJECT_ROOT / source_path
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None
