"""Tests for the video_script workflow wiring.

Covers the brand-selection helpers in lib.artifacts (style guides stay out of
the default bundle; video_style_block picks the right guide per brand and
degrades to a placeholder) and the new WorkflowInput fields.
"""

import pytest
from pydantic import ValidationError

from lib.artifacts import (
    DEFAULT_ARTIFACTS,
    KNOWN_ARTIFACTS,
    build_artifact_bundle,
    normalize_brand,
    video_style_block,
)
from lib.validation import WorkflowInput


def test_video_style_guides_known_but_excluded_from_default_bundle():
    for slug in ("video-style-guide", "video-style-guide-save-on-wireless"):
        assert slug in KNOWN_ARTIFACTS
        assert slug not in DEFAULT_ARTIFACTS


def test_video_style_guides_not_in_bundle_even_when_present():
    bundle = build_artifact_bundle({"video-style-guide": "video voice rules"})
    assert "video voice rules" not in bundle


def test_normalize_brand_defaults_to_navi():
    assert normalize_brand(None) == "navi"
    assert normalize_brand("") == "navi"


def test_normalize_brand_accepts_loose_spellings():
    assert normalize_brand("Navi") == "navi"
    assert normalize_brand("Save On Wireless") == "save-on-wireless"
    assert normalize_brand("save_on_wireless") == "save-on-wireless"
    assert normalize_brand("SOW") == "save-on-wireless"


def test_normalize_brand_rejects_unknown():
    with pytest.raises(ValueError, match="Unknown brand"):
        normalize_brand("verizon")


def test_video_style_block_selects_brand_guide():
    artifacts = {
        "video-style-guide": "navi rules",
        "video-style-guide-save-on-wireless": "sow rules",
    }
    assert video_style_block(artifacts, "navi") == "navi rules"
    assert video_style_block(artifacts, "save-on-wireless") == "sow rules"
    assert video_style_block(artifacts) == "navi rules"


def test_video_style_block_placeholder_when_absent():
    block = video_style_block({}, "navi")
    assert "No video style guide on file" in block


def test_workflow_input_brand_and_script_count_defaults():
    wi = WorkflowInput(topic="t")
    assert wi.brand is None
    assert wi.script_count == 3


def test_workflow_input_script_count_bounds():
    assert WorkflowInput(topic="t", script_count=2).script_count == 2
    with pytest.raises(ValidationError):
        WorkflowInput(topic="t", script_count=4)
    with pytest.raises(ValidationError):
        WorkflowInput(topic="t", script_count=1)
