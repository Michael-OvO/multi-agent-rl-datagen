"""Docs must not claim capabilities the code does not have.

Every pattern here was verified absent from forge/ during the 2026-07-14 audit.
If you implement one of these for real, delete its entry -- do not weaken the test.

Patterns are word-boundary regexes, not substrings: a bare "liar" substring also
matches "familiar" and "peculiar", which would fail this test for prose that
claims nothing.
"""

import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_DESIGN = _ROOT / "docs" / "DESIGN.md"

# (regex, human name, why it is a lie)
UNIMPLEMENTED_CLAIMS = [
    (r"\bz3\b", "z3", "no z3/CSP solver exists in forge/"),
    (r"\brandom[- ]valid\b", "random-valid", "no random-valid baseline exists in forge/"),
    (r"\bliar\b", "liar", "no liar dimension exists in forge/"),
    (r"\breward\.json\b", "reward.json", "the verifier writes reward.txt, not reward.json"),
    (r"\bheld[- ]out\b", "held-out", "no held-out config machinery exists in forge/"),
]


@pytest.mark.parametrize("pattern,name,why", UNIMPLEMENTED_CLAIMS)
def test_design_does_not_claim_unimplemented_feature(pattern, name, why):
    hits = re.findall(pattern, _DESIGN.read_text(), flags=re.IGNORECASE)
    assert not hits, f"DESIGN.md claims {name!r} ({len(hits)} hits) but {why}"


def test_design_is_not_marked_draft():
    assert "draft for review" not in _DESIGN.read_text().lower()


def test_design_code_fences_are_balanced():
    fences = [ln for ln in _DESIGN.read_text().splitlines() if ln.startswith("```")]
    assert len(fences) % 2 == 0, f"unclosed code fence: {len(fences)} fence markers"
