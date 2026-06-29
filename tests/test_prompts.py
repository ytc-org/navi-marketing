"""Tests for date injection in lib.prompts.render_prompt.

Covers the "wrong year" fix: every prompt gets current_date/current_year and a
date anchor prepended to the system prompt, so the model stops defaulting to a
training-era year.
"""

from datetime import date

from lib.prompts import Prompt, PromptConfig, render_prompt


def _prompt(system="You are an analyst.", user="Body"):
    return Prompt(config=PromptConfig(), system=system, user=user)


def test_current_date_and_year_available_as_variables():
    p = _prompt(user="On {{ current_date }} in {{ current_year }}.")
    r = render_prompt(p, {})
    today = date.today()
    assert today.isoformat() in r.user
    assert str(today.year) in r.user


def test_date_anchor_prepended_to_system_prompt():
    r = render_prompt(_prompt(), {})
    assert r.system.startswith("Current date:")
    assert "You are an analyst." in r.system


def test_caller_variables_still_render():
    p = _prompt(user="Topic: {{ topic }}")
    r = render_prompt(p, {"topic": "Prepaid Plans"})
    assert "Topic: Prepaid Plans" in r.user


def test_caller_can_override_injected_date_vars():
    p = _prompt(user="{{ current_year }}")
    r = render_prompt(p, {"current_year": "1999"})
    assert "1999" in r.user


def test_empty_system_prompt_gets_no_anchor():
    """Don't prepend a date line to a prompt that has no system message."""
    r = render_prompt(_prompt(system="", user="x"), {})
    assert r.system == ""


def test_unknown_placeholder_left_intact():
    p = _prompt(user="keep {{ unknown }} as-is")
    r = render_prompt(p, {})
    assert "{{ unknown }}" in r.user
