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


# Artifacts that carry no brand context the model needs in a prompt
# (workflow-context is operating instructions for the ops system itself).
_DEFAULT_EXCLUDED = {"workflow-context"}

# Default selection: every known artifact except the operating-context file.
DEFAULT_ARTIFACTS = [n for n in KNOWN_ARTIFACTS if n not in _DEFAULT_EXCLUDED]


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
