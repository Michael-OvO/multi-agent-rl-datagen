"""Charter parsing, and the refusal that keeps ownership human.

A charter draft may be written by an agent -- by hand or by the brainstorm
pathway -- but it has no effect until Michael queues it, and the queue action
is the approval. `status: draft` is what makes that gate mechanical rather
than a convention someone remembers.
"""

from __future__ import annotations

import pytest

from forge.factory.charter import parse_charter

APPROVED = """---
status: ready
owner: michael
ability: capability-discovery
budget_tokens: 5000000
---

# Charter: the hidden knower

**Capability claim.** A coordinator can identify which teammate can know a fact.
"""

DRAFT = APPROVED.replace("status: ready", "status: draft")


def test_an_approved_charter_parses_its_front_matter_and_body():
    charter = parse_charter(APPROVED, slug="hidden-knower")
    assert charter.slug == "hidden-knower"
    assert charter.owner == "michael"
    assert charter.ability == "capability-discovery"
    assert charter.budget_tokens == 5000000
    assert "Capability claim" in charter.body
    assert "---" not in charter.body, "front-matter must not leak into the body"


def test_a_draft_charter_is_refused_by_name():
    with pytest.raises(SystemExit, match="draft"):
        parse_charter(DRAFT, slug="hidden-knower")


def test_a_charter_without_an_owner_is_refused():
    text = APPROVED.replace("owner: michael\n", "")
    with pytest.raises(SystemExit, match="owner"):
        parse_charter(text, slug="hidden-knower")


def test_a_charter_with_no_front_matter_is_refused():
    with pytest.raises(SystemExit, match="front-matter"):
        parse_charter("# Just a heading\n", slug="hidden-knower")


def test_an_empty_body_is_refused():
    text = "---\nstatus: ready\nowner: michael\n---\n\n   \n"
    with pytest.raises(SystemExit, match="body"):
        parse_charter(text, slug="hidden-knower")


def test_the_optional_fields_default_cleanly():
    text = "---\nstatus: ready\nowner: michael\n---\n\nA claim.\n"
    charter = parse_charter(text, slug="s")
    assert charter.ability is None
    assert charter.budget_tokens is None
