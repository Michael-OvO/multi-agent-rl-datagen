"""The write-up must not claim more than the repository measured.

Every claim here was verified against `forge/` or against a file in `sweep/`.
These are not style checks: each one is a specific overclaim this repo actually
published and had to withdraw.

  * "51 tasks x 8 configurations = 408 variants" sat three paragraphs from the
    section saying `chain` was unimplemented and unsolvable.
  * "Three tasks" described a sweep containing two.
  * "118 passed" was wrong by the next commit.
  * The do-nothing floor was stated as 0.167 after the fix that moved it to
    0.333 -- which is also the number every partitioned config scored.

Patterns are word-boundary regexes, not substrings: a bare "liar" substring also
matches "familiar" and "peculiar", which would fail this test for prose that
claims nothing.
"""

import json
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_DOC = _ROOT / "WRITEUP.md"
_SWEEP = _ROOT / "sweep"

_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}

# (regex, human name, why it is a lie)
UNIMPLEMENTED_CLAIMS = [
    (r"\bz3\b", "z3", "no z3/CSP solver exists in forge/"),
    (r"\brandom[- ]valid\b", "random-valid", "no random-valid baseline exists in forge/"),
    (r"\bliar\b", "liar", "no liar dimension exists in forge/"),
    (r"\breward\.json\b", "reward.json", "the verifier writes reward.txt, not reward.json"),
    (r"\bheld[- ]out\b", "held-out", "no held-out config machinery exists in forge/"),
]


@pytest.mark.parametrize("pattern,name,why", UNIMPLEMENTED_CLAIMS)
def test_the_writeup_does_not_claim_an_unimplemented_feature(pattern, name, why):
    hits = re.findall(pattern, _DOC.read_text(), flags=re.IGNORECASE)
    assert not hits, f"WRITEUP.md claims {name!r} ({len(hits)} hits) but {why}"


def test_the_writeup_is_not_marked_draft():
    assert "draft for review" not in _DOC.read_text().lower()


def test_the_writeup_code_fences_are_balanced():
    fences = [ln for ln in _DOC.read_text().splitlines() if ln.startswith("```")]
    assert len(fences) % 2 == 0, f"unclosed code fence: {len(fences)} fence markers"


def test_there_is_exactly_one_deep_document():
    """WRITEUP.md and docs/DESIGN.md duplicated each other section for section.

    Two documents saying the same thing is two documents to keep true, and the
    one that drifts is the one nobody is reading. There is one now.
    """
    assert not (_ROOT / "docs" / "DESIGN.md").exists(), (
        "docs/DESIGN.md is back; it duplicated WRITEUP.md and drifted"
    )


# -- claims that must match the code -----------------------------------------


def test_the_scale_claim_counts_only_configurations_that_ship():
    """The scale headline must be an inventory, not a ceiling in its clothes."""
    from forge.appworld.cli import SHIPPED_CONFIGS

    text = _DOC.read_text()
    # \s+ rather than a literal space: the claim wraps across lines in markdown.
    m = re.search(r"51 tasks × (\d+) shipped configurations\s*=\s*(\d+)\s*variants",
                  text)
    assert m, "the scale claim must state the shipped configuration count explicitly"
    assert int(m.group(1)) == len(SHIPPED_CONFIGS), (
        f"the write-up claims {m.group(1)} shipped configurations; "
        f"cli.SHIPPED_CONFIGS has {len(SHIPPED_CONFIGS)}"
    )
    assert int(m.group(2)) == 51 * len(SHIPPED_CONFIGS)


# -- claims that must match the evidence -------------------------------------


def test_the_writeup_states_the_do_nothing_floor_it_measured():
    """The floor is the number the headline turned out to be."""
    rows = json.loads((_SWEEP / "appworld_donothing.json").read_text())
    floors = {r["partial"] for r in rows}
    assert len(floors) == 1, f"the floor is not a single number: {floors}"
    floor = floors.pop()

    text = _DOC.read_text()
    assert f"do-nothing floor is 2/6 = {floor}" in text, (
        f"the write-up must state the measured do-nothing floor ({floor})"
    )
    assert "0.167 = 1/6 = did nothing" not in text, (
        "that was the pre-fix floor and is no longer true"
    )


def test_the_headline_measurement_matches_the_sweep_it_rests_on():
    """§5's table must be the sweep, not a memory of it.

    Every previous version of this claim drifted from its evidence: "three
    tasks" for a two-task sweep, and a partition effect that was a harness bug.
    """
    rows = json.loads((_SWEEP / "appworld_knobs_v3.json").read_text())
    text = _DOC.read_text()

    tasks = sorted({r["task_id"] for r in rows})
    m = re.search(r"\*\*(\w+) tasks\*\* \(([^)]+)\)", text)
    assert m, "§5 must name the tasks it measured"
    assert _WORDS[m.group(1).lower()] == len(tasks), (
        f"§5 says {m.group(1)} tasks; appworld_knobs_v3.json has {len(tasks)}"
    )
    assert re.findall(r"2a163ab_\d", m.group(2)) == tasks

    # The control and the partitioned arms, as measured.
    def mean(cfg):
        vals = [r["partial"] for r in rows if r["config"].startswith(cfg)]
        return round(sum(vals) / len(vals), 3) if vals else None

    for cfg in ("open", "star-docs", "star-names"):
        got = mean(cfg)
        assert got is not None, f"the sweep has no {cfg} rows"
        assert f"{got:.3f}" in text, (
            f"§5 does not state the measured {cfg} score of {got:.3f}"
        )


def test_the_writeup_states_the_partition_result_it_measured():
    """If open == star, the write-up must say so in those words.

    This is the repo's own rule -- a knob that does not move the score against
    the OPEN control is decoration -- applied to its own headline. A write-up
    that reports the sweep in a table and then talks around it in the prose is
    the failure this whole document is about.
    """
    rows = json.loads((_SWEEP / "appworld_knobs_v3.json").read_text())
    partitioned = [r["partial"] for r in rows if r["config"].startswith("star")]
    control = [r["partial"] for r in rows if r["config"].startswith("open")]
    if not (partitioned and control):
        pytest.skip("sweep incomplete")

    text = _DOC.read_text().lower()
    if round(sum(partitioned) / len(partitioned), 3) >= round(
            sum(control) / len(control), 3):
        assert "decoration" in text, (
            "the partition did not beat the control; the write-up must say what "
            "that means under its own stated rule"
        )


def test_the_readme_does_not_pin_a_test_count():
    # "118 passed" was wrong by the next commit, and wrong again by the one
    # after. A number that rots on every change is a liability, not evidence.
    readme = (_ROOT / "README.md").read_text()
    assert not re.search(r"\d+\s+passed", readme), (
        "README pins a test count, which is stale the moment a test is added"
    )


# -- the argument the method rests on ----------------------------------------


def test_the_writeup_keeps_the_v1_retrospective_rather_than_hiding_it():
    """v1 built the world AND the judge, and `theory-of-mind` scored 12/12 with
    zero gradient. The current design refuses to design an oracle *because of
    that*, so the retrospective is the argument, not an appendix. A write-up that
    presents the method without the failure that forced it will drift back to
    writing generators.
    """
    text = _DOC.read_text()
    assert "12 of 12" in text, "the ToM degeneracy result must survive"
    assert "seed brute-force" in text, "the exploit that broke every dimension must survive"
    assert "manufacture constraints" in text.lower(), "the principle must be stated"
