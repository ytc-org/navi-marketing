"""Anthropic API wrapper with retry logic."""

from __future__ import annotations

import os
import time

import anthropic


def _get_client() -> anthropic.Anthropic:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set. Add it to your .env file.")
    return anthropic.Anthropic(api_key=api_key)


def call_claude(
    *,
    system: str,
    user: str,
    model: str = "claude-haiku-4-5",
    temperature: float = 0.2,
    max_tokens: int = 4096,
    max_retries: int = 3,
) -> str:
    """Send a single system+user message to Claude and return the text response.

    Retries transient failures (rate limits, overloaded, timeouts) with
    exponential backoff. Raises on permanent errors.
    """
    client = _get_client()
    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            # Extract text from content blocks
            return "".join(
                block.text for block in response.content if block.type == "text"
            )

        except anthropic.RateLimitError as exc:
            last_error = exc
            wait = 2 ** attempt * 5  # 5s, 10s, 20s
            print(f"  Rate limited (attempt {attempt + 1}/{max_retries}). Waiting {wait}s...")
            time.sleep(wait)

        except anthropic.APIStatusError as exc:
            if exc.status_code in (429, 503, 529):
                last_error = exc
                wait = 2 ** attempt * 5
                print(f"  Transient error {exc.status_code} (attempt {attempt + 1}/{max_retries}). Waiting {wait}s...")
                time.sleep(wait)
            else:
                raise

        except anthropic.APIConnectionError as exc:
            last_error = exc
            wait = 2 ** attempt * 3
            print(f"  Connection error (attempt {attempt + 1}/{max_retries}). Waiting {wait}s...")
            time.sleep(wait)

    raise RuntimeError(f"Failed after {max_retries} attempts. Last error: {last_error}")
