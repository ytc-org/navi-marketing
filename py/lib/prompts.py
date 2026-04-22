"""Load prompt templates with YAML frontmatter and render variables."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


@dataclass
class PromptConfig:
    """Metadata parsed from the YAML frontmatter of a .md prompt file."""

    provider: str = "anthropic"
    model: str = "claude-haiku-4-5"
    temperature: float = 0.2
    max_tokens: int = 4096


@dataclass
class Prompt:
    """A fully parsed prompt ready for LLM invocation."""

    config: PromptConfig
    system: str
    user: str


def load_prompt(name: str, prompts_dir: Path | None = None) -> Prompt:
    """Load a prompt file by name (without extension) and parse it.

    Expected format:
        ---
        provider: anthropic
        model: claude-haiku-4-5
        temperature: 0.2
        maxTokens: 4096
        ---

        <system>
        ...system message...
        </system>

        <user>
        ...user message...
        </user>
    """
    prompts_dir = prompts_dir or PROMPTS_DIR
    path = prompts_dir / f"{name}.md"
    if not path.is_file():
        raise FileNotFoundError(f"Prompt file not found: {path}")

    raw = path.read_text(encoding="utf-8")

    # Parse YAML frontmatter
    config = PromptConfig()
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", raw, re.DOTALL)
    if fm_match:
        fm = yaml.safe_load(fm_match.group(1)) or {}
        config.provider = fm.get("provider", config.provider)
        config.model = fm.get("model", config.model)
        config.temperature = float(fm.get("temperature", config.temperature))
        config.max_tokens = int(fm.get("maxTokens", fm.get("max_tokens", config.max_tokens)))
        raw = raw[fm_match.end():]

    # Extract <system> and <user> blocks
    system = _extract_tag(raw, "system")
    user = _extract_tag(raw, "user")

    return Prompt(config=config, system=system, user=user)


def render_prompt(prompt: Prompt, variables: dict[str, str]) -> Prompt:
    """Render Jinja2-style {{ variable }} placeholders in the system and user strings.

    Returns a new Prompt with rendered content. Uses simple string replacement
    rather than a full Jinja2 engine to avoid the dependency.
    """
    rendered_system = _render_template(prompt.system, variables)
    rendered_user = _render_template(prompt.user, variables)
    return Prompt(config=prompt.config, system=rendered_system, user=rendered_user)


def _extract_tag(text: str, tag: str) -> str:
    """Pull content from between <tag>...</tag> markers."""
    pattern = rf"<{tag}>\s*(.*?)\s*</{tag}>"
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        return ""
    return match.group(1).strip()


def _render_template(template: str, variables: dict[str, str]) -> str:
    """Replace {{ key }} placeholders with values from the variables dict."""
    def replacer(match: re.Match) -> str:
        key = match.group(1).strip()
        return str(variables.get(key, match.group(0)))

    return re.sub(r"\{\{\s*(\w+)\s*\}\}", replacer, template)
