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


def build_artifact_bundle(artifacts: dict[str, str]) -> str:
    """Format all artifacts into a single Markdown string for prompt injection.

    Known artifacts appear first in a stable order, followed by any extras.
    """
    sections: list[str] = []

    for name in KNOWN_ARTIFACTS:
        content = artifacts.get(name)
        if content:
            sections.append(f"## {_heading(name)}\n{content.strip()}")

    for name, content in artifacts.items():
        if name not in KNOWN_ARTIFACTS and content:
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
