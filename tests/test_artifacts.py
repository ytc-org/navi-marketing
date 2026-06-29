"""Tests for the optional-artifact wiring in lib.artifacts.

Covers the pricing-context and feedback-loop additions: plans-and-pricing flows
into the default bundle; recommendation-guardrails is injected separately as a
suppression list (and degrades to a neutral placeholder when absent).
"""

from lib.artifacts import (
    DEFAULT_ARTIFACTS,
    KNOWN_ARTIFACTS,
    build_artifact_bundle,
    recommendation_guardrails_block,
)


def test_pricing_artifact_in_default_bundle():
    assert "plans-and-pricing" in KNOWN_ARTIFACTS
    assert "plans-and-pricing" in DEFAULT_ARTIFACTS


def test_guardrails_artifact_known_but_excluded_from_default_bundle():
    assert "recommendation-guardrails" in KNOWN_ARTIFACTS
    assert "recommendation-guardrails" not in DEFAULT_ARTIFACTS


def test_pricing_renders_in_bundle_when_present():
    bundle = build_artifact_bundle({"plans-and-pricing": "| Plan | $XX |"})
    assert "Plans And Pricing" in bundle  # title-cased heading
    assert "| Plan | $XX |" in bundle


def test_guardrails_not_in_default_bundle_even_when_present():
    bundle = build_artifact_bundle({"recommendation-guardrails": "suppress X"})
    assert "suppress X" not in bundle


def test_guardrails_block_placeholder_when_absent():
    assert recommendation_guardrails_block({}) == "No recommendation guardrails on file."


def test_guardrails_block_placeholder_when_empty_string():
    assert recommendation_guardrails_block({"recommendation-guardrails": "   "}) == (
        "No recommendation guardrails on file."
    )


def test_guardrails_block_returns_stripped_content():
    assert recommendation_guardrails_block(
        {"recommendation-guardrails": "  Do not flag X.  "}
    ) == "Do not flag X."
