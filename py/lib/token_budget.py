"""Per-model, per-direction sliding-window throttler for LLM calls.

Anthropic enforces rate limits **separately per model class** and **separately
for input vs output tokens** (see platform.claude.com/docs/en/api/rate-limits).
There is no single combined tokens-per-minute cap.

This module mirrors that reality: each model class (opus / sonnet / haiku) gets
independent ITPM (input), OTPM (output), and RPM (request) sliding windows. A
single process-level instance is shared across concurrent workflows so they
cooperatively stay under each model's caps.

Why this matters: at Tier 1, Opus has 500k ITPM / 80k OTPM — effectively
unlimited for this workload — while Sonnet is only 30k ITPM / 8k OTPM. Pooling
all models into one budget would needlessly throttle Opus calls and mis-size
the Sonnet ones.
"""

from __future__ import annotations

import os
import threading
import time
from collections import deque
from dataclasses import dataclass


class TokenBudgetExceededError(RuntimeError):
    """Raised when a single call cannot fit within a model's per-minute budget.

    Surfaces unrunnable calls instead of wedging the throttler forever — the
    fix lives in the workflow/prompt (smaller input, or a model with a higher
    limit), not here.
    """


@dataclass(frozen=True)
class ModelLimits:
    """Per-minute limits for one model class."""

    itpm: int  # input tokens per minute
    otpm: int  # output tokens per minute
    rpm: int   # requests per minute


# Anthropic standard-tier rate limits, per model class.
# Source: https://platform.claude.com/docs/en/api/rate-limits
TIER_LIMITS: dict[str, dict[str, ModelLimits]] = {
    "1": {
        "opus":   ModelLimits(itpm=500_000, otpm=80_000, rpm=50),
        "sonnet": ModelLimits(itpm=30_000,  otpm=8_000,  rpm=50),
        "haiku":  ModelLimits(itpm=50_000,  otpm=10_000, rpm=50),
    },
    "2": {
        "opus":   ModelLimits(itpm=2_000_000, otpm=200_000, rpm=1_000),
        "sonnet": ModelLimits(itpm=450_000,   otpm=90_000,  rpm=1_000),
        "haiku":  ModelLimits(itpm=450_000,   otpm=90_000,  rpm=1_000),
    },
    "3": {
        "opus":   ModelLimits(itpm=5_000_000, otpm=400_000, rpm=2_000),
        "sonnet": ModelLimits(itpm=800_000,   otpm=160_000, rpm=2_000),
        "haiku":  ModelLimits(itpm=1_000_000, otpm=200_000, rpm=2_000),
    },
    "4": {
        "opus":   ModelLimits(itpm=10_000_000, otpm=800_000, rpm=4_000),
        "sonnet": ModelLimits(itpm=2_000_000,  otpm=400_000, rpm=4_000),
        "haiku":  ModelLimits(itpm=4_000_000,  otpm=800_000, rpm=4_000),
    },
}


def classify_model(model: str) -> str:
    """Map a model id to its rate-limit class (opus / sonnet / haiku).

    Unknown models fall back to 'sonnet' — the tightest limits — so an
    unrecognized model is throttled conservatively rather than not at all.
    """
    m = (model or "").lower()
    if "opus" in m:
        return "opus"
    if "haiku" in m:
        return "haiku"
    if "sonnet" in m:
        return "sonnet"
    return "sonnet"


class _Window:
    """A sliding-window counter over `window_seconds`.

    Tracks (timestamp, amount) events and answers "how long until `amount`
    more would fit under `limit`".
    """

    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = max(0, limit)
        self.window = window_seconds
        self._events: deque[tuple[float, int]] = deque()

    def _prune(self, now: float) -> None:
        cutoff = now - self.window
        while self._events and self._events[0][0] < cutoff:
            self._events.popleft()

    def used(self, now: float) -> int:
        self._prune(now)
        return sum(amount for _, amount in self._events)

    def time_until_fits(self, amount: float, now: float) -> float:
        """Seconds until `amount` fits under the limit. 0.0 if it fits now."""
        self._prune(now)
        used = sum(a for _, a in self._events)
        if used + amount <= self.limit:
            return 0.0
        need_to_free = (used + amount) - self.limit
        freed = 0
        for ts, amt in self._events:
            freed += amt
            if freed >= need_to_free:
                return max(ts + self.window - now, 0.0)
        return float(self.window)

    def record(self, amount: int, now: float) -> None:
        if amount > 0:
            self._events.append((now, amount))
        self._prune(now)


class _ModelBudget:
    """ITPM + OTPM + RPM windows for one model class."""

    def __init__(self, limits: ModelLimits, window_seconds: int, safety_margin: float) -> None:
        self.limits = limits
        self.input = _Window(int(limits.itpm * safety_margin), window_seconds)
        self.output = _Window(int(limits.otpm * safety_margin), window_seconds)
        # Requests are integer and rarely the binding constraint; no margin.
        self.requests = _Window(limits.rpm, window_seconds)


class TokenBudget:
    def __init__(
        self,
        tier: str = "1",
        window_seconds: int = 60,
        safety_margin: float = 0.9,
        output_ratio: float = 0.6,
    ) -> None:
        if tier not in TIER_LIMITS:
            raise ValueError(f"Unknown tier {tier!r}. Expected one of {sorted(TIER_LIMITS)}.")
        if not (0 < safety_margin <= 1):
            raise ValueError("safety_margin must be in (0, 1]")
        if not (0 < output_ratio <= 1):
            raise ValueError("output_ratio must be in (0, 1]")
        self.tier = tier
        self.window = window_seconds
        self.safety_margin = safety_margin
        self.output_ratio = output_ratio
        self._lock = threading.Lock()
        self._models: dict[str, _ModelBudget] = {
            name: _ModelBudget(limits, window_seconds, safety_margin)
            for name, limits in TIER_LIMITS[tier].items()
        }

    def wait_for_budget(
        self, model: str, input_tokens: int, max_output_tokens: int
    ) -> float:
        """Block until this call fits the model's ITPM/OTPM/RPM windows.

        Returns total seconds slept (0.0 if no wait was needed).
        Raises TokenBudgetExceededError if the call alone can never fit.
        """
        cls = classify_model(model)
        input_tokens = max(0, input_tokens)
        output_estimate = int(max(0, max_output_tokens) * self.output_ratio)

        with self._lock:
            mb = self._models[cls]
            if input_tokens > mb.input.limit:
                raise TokenBudgetExceededError(
                    f"Call to {cls} estimated at {input_tokens} input tokens exceeds "
                    f"the effective ITPM budget of {mb.input.limit} "
                    f"(tier {self.tier} raw {mb.limits.itpm}). Reduce input size."
                )
            if output_estimate > mb.output.limit:
                raise TokenBudgetExceededError(
                    f"Call to {cls} estimated at {output_estimate} output tokens "
                    f"(max_tokens {max_output_tokens} x {self.output_ratio}) exceeds "
                    f"the effective OTPM budget of {mb.output.limit} "
                    f"(tier {self.tier} raw {mb.limits.otpm}). Lower max_tokens or "
                    f"use a model with a higher OTPM limit."
                )

        total_slept = 0.0
        while True:
            with self._lock:
                mb = self._models[cls]
                now = time.monotonic()
                wait = max(
                    mb.input.time_until_fits(input_tokens, now),
                    mb.output.time_until_fits(output_estimate, now),
                    mb.requests.time_until_fits(1, now),
                )
                if wait <= 0:
                    return total_slept
            # Pad slightly so the target event has aged out by the recheck.
            sleep_for = wait + 0.05
            time.sleep(sleep_for)
            total_slept += sleep_for

    def record(self, model: str, input_tokens: int, output_tokens: int) -> None:
        """Record actual tokens consumed by a completed (or failed) call."""
        cls = classify_model(model)
        with self._lock:
            now = time.monotonic()
            mb = self._models[cls]
            mb.input.record(max(0, input_tokens), now)
            mb.output.record(max(0, output_tokens), now)
            mb.requests.record(1, now)

    def snapshot(self, model: str) -> dict:
        """Per-model window state, for logging."""
        cls = classify_model(model)
        with self._lock:
            now = time.monotonic()
            mb = self._models[cls]
            return {
                "class": cls,
                "tier": self.tier,
                "input_used": mb.input.used(now),
                "input_limit": mb.input.limit,
                "output_used": mb.output.used(now),
                "output_limit": mb.output.limit,
                "requests_used": mb.requests.used(now),
                "requests_limit": mb.requests.limit,
            }


_BUDGET = TokenBudget(
    tier=os.getenv("ANTHROPIC_RATE_LIMIT_TIER", "1"),
    output_ratio=float(os.getenv("ANTHROPIC_OUTPUT_RATIO", "0.6")),
)


def get_budget() -> TokenBudget:
    return _BUDGET


def estimate_tokens_from_text(text: str) -> int:
    """Fast char-based token estimate (~4 chars/token, per Anthropic docs)."""
    if not text:
        return 0
    return max(1, len(text) // 4)
