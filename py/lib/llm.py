"""Anthropic API wrapper with retry logic and per-model rate-limit throttling."""

from __future__ import annotations

import os
import time

import anthropic

from .token_budget import (
    TokenBudgetExceededError,
    estimate_tokens_from_text,
    get_budget,
)


def _get_client() -> anthropic.Anthropic:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set. Add it to your .env file.")
    return anthropic.Anthropic(api_key=api_key)


def _count_input_tokens(
    client: anthropic.Anthropic, model: str, system: str, user: str
) -> int:
    """Exact input token count via the API's count_tokens endpoint.

    The char-based heuristic can undershoot badly on dense content (markdown,
    URLs, tables tokenize at ~3 chars/token, not ~4), which would let the
    throttler wave through a call that breaches the real rate limit. The
    count_tokens endpoint is exact and does not consume the ITPM/OTPM budget.
    Falls back to the heuristic if the call fails for any reason.
    """
    try:
        counted = client.messages.count_tokens(
            model=model,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return counted.input_tokens
    except Exception:
        return estimate_tokens_from_text(system) + estimate_tokens_from_text(user)


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

    Calls are throttled by a shared per-model token budget (see
    `py/lib/token_budget.py`). Anthropic rate-limits each model class
    independently for input (ITPM) and output (OTPM) tokens, so the throttler
    tracks opus / sonnet / haiku separately — an Opus call is not slowed by
    Sonnet traffic. Retries transient failures with exponential backoff.
    """
    client = _get_client()
    budget = get_budget()
    input_estimate = _count_input_tokens(client, model, system, user)

    slept = budget.wait_for_budget(
        model=model,
        input_tokens=input_estimate,
        max_output_tokens=max_tokens,
    )
    if slept > 0:
        snap = budget.snapshot(model)
        print(
            f"  [throttle] slept {slept:.1f}s on {snap['class']} "
            f"(in {snap['input_used']}/{snap['input_limit']}, "
            f"out {snap['output_used']}/{snap['output_limit']})"
        )

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
            in_tokens = getattr(response.usage, "input_tokens", 0) or 0
            out_tokens = getattr(response.usage, "output_tokens", 0) or 0
            budget.record(model, in_tokens, out_tokens)
            snap = budget.snapshot(model)
            print(
                f"  [tokens] {snap['class']} in={in_tokens} out={out_tokens} "
                f"(window in {snap['input_used']}/{snap['input_limit']}, "
                f"out {snap['output_used']}/{snap['output_limit']})"
            )
            return "".join(
                block.text for block in response.content if block.type == "text"
            )

        except anthropic.RateLimitError as exc:
            last_error = exc
            # Account for the failed attempt so the windows reflect it.
            budget.record(model, input_estimate, int(max_tokens * budget.output_ratio))
            wait = 2 ** attempt * 5  # 5s, 10s, 20s
            print(f"  Rate limited (attempt {attempt + 1}/{max_retries}). Waiting {wait}s...")
            time.sleep(wait)

        except anthropic.APIStatusError as exc:
            if exc.status_code in (429, 503, 529):
                last_error = exc
                if exc.status_code == 429:
                    budget.record(model, input_estimate, int(max_tokens * budget.output_ratio))
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


__all__ = ["call_claude", "TokenBudgetExceededError"]
