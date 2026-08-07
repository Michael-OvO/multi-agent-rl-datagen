"""The write-up must not claim more than the repository measured.

Every claim here was verified against `forge/` or against a file in `sweep/`.
These are not style checks: each one is a specific overclaim this repo actually
published and had to withdraw.

  * "51 tasks x 8 configurations = 408 variants" counted tasks rejected by the
    information-seam gate and configurations that do not ship.
  * "Three tasks" described a sweep containing two.
  * "118 passed" was wrong by the next commit.
  * The do-nothing floor was stated as 0.167 after the fix that moved it to
    0.333 -- which is also the number every partitioned config scored.

Patterns are word-boundary regexes, not substrings: a bare "liar" substring also
matches "familiar" and "peculiar", which would fail this test for prose that
claims nothing.

**This module guards two substrates, and the naming carries the difference.**
`test_the_writeup_*` guards `WRITEUP.md`, which documents the AppWorld work and
was deliberately not migrated -- it is the engineering log of a finished
substrate, so its numbers are history and must stay pinned to `appworld_*.json`.
`test_the_report_*` guards `docs/*.tex`, which were migrated to Gaia2 and pin to
`gaia2_*.json`. Two guards therefore assert opposite polarity on the same
concept and both are correct: the write-up must *state* the do-nothing floor it
measured, and the reports must state that no such floor has been measured on
their substrate. Read the prefix before concluding one of them is stale.
"""

import functools
import json
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SWEEP = _ROOT / "sweep"

# -- WRITEUP.md: the AppWorld substrate, deliberately not migrated ------------
#
# Everything from here to the "-- the reports --" banner guards WRITEUP.md and
# reads appworld_*.json. That is not drift: the write-up is the log of what the
# AppWorld work measured, so re-pointing it at Gaia2 evidence would falsify a
# record rather than update one.

_DOC = _ROOT / "WRITEUP.md"

_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}

#: The sweep §5 rests on. Named once: the write-up, the README and these
#: assertions have to move together or the guard checks a file the prose
#: stopped citing -- which is how "three tasks" came to describe a sweep of
#: two, and how v3's means outlived the code path that produced them.
_SWEEP_FILE = "appworld_knobs_v5.json"

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
    seams = json.loads((_SWEEP / "appworld_seams.json").read_text())
    pool = sum(bool(row["seams"]) for row in seams)
    # \s+ rather than a literal space: the claim wraps across lines in markdown.
    m = re.search(
        rf"{pool} tasks × (\d+) shipped configurations\s*=\s*(\d+)\s*variants",
        text,
    )
    assert m, "the scale claim must state the shipped configuration count explicitly"
    assert int(m.group(1)) == len(SHIPPED_CONFIGS), (
        f"the write-up claims {m.group(1)} shipped configurations; "
        f"cli.SHIPPED_CONFIGS has {len(SHIPPED_CONFIGS)}"
    )
    assert int(m.group(2)) == pool * len(SHIPPED_CONFIGS)


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
    rows = json.loads((_SWEEP / _SWEEP_FILE).read_text())
    text = _DOC.read_text()

    tasks = sorted({r["task_id"] for r in rows})
    m = re.search(r"\*\*(\w+) tasks\*\* \(([^)]+)\)", text)
    assert m, "§5 must name the tasks it measured"
    assert _WORDS[m.group(1).lower()] == len(tasks), (
        f"§5 says {m.group(1)} tasks; {_SWEEP_FILE} has {len(tasks)}"
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
    rows = json.loads((_SWEEP / _SWEEP_FILE).read_text())
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

    # ... and it must still be true of the data. The evidence for this claim was
    # deleted once already (31bd588, "drop the orphaned measurements for the
    # quarantined dimensions"), leaving section 1's load-bearing number as the
    # least checkable one in the document while this guard pinned only the prose.
    rows = json.loads((_SWEEP / "tom_degeneracy.json").read_text())
    runs = [r[m] for r in rows for m in ("gpt56", "gpt41")]
    assert len(runs) == 12, f"the claim says 12 runs; the file has {len(runs)}"
    assert all(r == 1.0 for r in runs), (
        f"12 of 12 at reward 1.0 is the whole of section 1; the file says {runs}"
    )
    assert "seed brute-force" in text, "the exploit that broke every dimension must survive"
    assert "manufacture constraints" in text.lower(), "the principle must be stated"


# -- the reports -------------------------------------------------------------
#
# docs/*.tex is the artefact that gets handed to a reader, and until now it was
# the only document nothing checked. Its numbers come from the same files
# WRITEUP.md's do, so they can rot the same way -- and the regressions this
# module's docstring memorialises ("a partition effect that was a harness bug",
# "'three tasks' described a sweep containing two") are exactly the species a
# report drifts into once the sweep beneath it moves.
#
# There are now two of them, and they carry the same numbers. A translation is
# exactly where a number rots unobserved: nobody rereads the version they do not
# speak, and the sweep moves under both. So every check here runs against both,
# and each report supplies its own phrasings.

_TEX_ZH = _ROOT / "docs" / "multi_agent_rl_data_generation_zh.tex"
_TEX_EN = _ROOT / "docs" / "multi_agent_rl_data_generation_en.tex"

#: Per-report phrasings for the checks below, keyed by the id pytest shows on
#: failure. `cells`/`scenarios`/`tasks_banned` take the computed count; the
#: rest are matched literally.
_REPORTS = {
    "zh": {
        "path": _TEX_ZH,
        "cells": "{n} 个实例",
        "scenarios": "{n} 个信息缝场景",
        "tasks_banned": "{n} 个协作任务",
        "chain_unbuilt": "未实现",
        "insufficient": "拒绝给出",
        "floor_unmeasured": "无动作探针",
        "floor_negations": ("还没有跑过", "尚未被执行", "都还没做"),
        "overclaims": (
            "这说明更有价值的难度来自角色能力未知",
            "初步难度梯度",
            "展示出从 open 到 star-docs、再到 star-names",
            "权限划分是免费的",
        ),
    },
    "en": {
        "path": _TEX_EN,
        "cells": "{n} cells",
        "scenarios": "{n} seamful scenarios",
        "tasks_banned": "{n} collaborative tasks",
        "chain_unbuilt": "not built",
        "insufficient": "no verdict",
        "floor_unmeasured": "do-nothing probe",
        "floor_negations": ("has not been run", "have not been run", "neither has been done"),
        # No drift history here yet -- the zh list memorialises real regressions,
        # this one is the same property stated forward, in the phrasings an
        # English rewrite would reach for first.
        "overclaims": (
            "role opacity is the more effective source of difficulty",
            "preliminary difficulty gradient",
            "a difficulty gradient from open to star-docs",
            "the partition is free",
        ),
    },
}


@functools.cache
def _campaign() -> dict:
    """The whole campaign document: `summary` by cell type, plus `rows`.

    One owner for the filename, for the reason the `_SWEEP_FILE` comment above
    gives: a guard that names its evidence in three places is a guard that can
    end up checking a file the prose stopped citing. Cached because the
    document is invariant for the session and every guard here is parametrized
    over two reports.
    """
    return json.loads((_SWEEP / "gaia2_full_campaign.json").read_text())


def _sentences(text: str) -> list[str]:
    """Sentence-ish spans of a report.

    Anchoring a claim to a *line* is nearly no anchor in LaTeX: a .tex
    paragraph is one physical line running to several hundred words, so a
    co-occurrence check passes on any two facts that happen to share a
    paragraph. Verified, not assumed -- the mutation "a do-nothing probe
    returned a floor of 0.081" survived the line-level check, rescued by an
    unrelated "neither has been done" four sentences later in the same
    paragraph. Markdown lines are short enough that the distinction never came
    up; .tex is where it bites.

    CJK terminators need no trailing space; ASCII ones do, which keeps decimals
    like `0.081` from splitting mid-number.
    """
    return re.split(r"(?<=[.!?])\s+|(?<=[。！？])", text)


@functools.cache
def _seamful_scenarios() -> int:
    """Unique scenarios that cleared the seam gate, across every mined split."""
    ids = set()
    for name in ("gaia2_mini_admission.json", "gaia2_adaptability_admission.json"):
        for row in json.loads((_SWEEP / name).read_text()):
            if row["seamful"]:
                ids.add(row["scenario_id"])
    return len(ids)


_reports = pytest.mark.parametrize("report", _REPORTS.values(), ids=_REPORTS.keys())


@_reports
def test_the_report_multiplies_the_candidate_pool_the_seam_gate_actually_leaves(report):
    """The multiplicand is the seam-filtered pool, not the strict-filtered one.

    This test used to hardcode the count *before* the seam gate ran, which is
    the number the yield section exists to retire: most multi-app tasks carry no
    information seam, so multiplying by the strict-filtered pool re-inflates it
    by exactly the fraction the gate was built to remove. Derive it from the
    measurement instead, so the report and the gate cannot drift apart again.
    """
    text = report["path"].read_text()
    pool = _seamful_scenarios()
    # Tuple, not concatenation: `a` + `bc` and `ab` + `c` are the same string,
    # and a dedupe key that can collide undercounts in exactly the flattering
    # direction. The campaign writer keys on the same pair.
    cells = {(r["scenario_id"], r["cell_type"]) for r in _campaign()["rows"]}

    assert report["scenarios"].format(n=pool) in text, (
        f"the report must state the seam-filtered pool ({pool} scenarios)"
    )
    assert report["cells"].format(n=len(cells)) in text, (
        f"the report must say {len(cells)} cells for {pool} seamful scenarios"
    )
    # The cell count counts configurations, not tasks. Calling them tasks is the
    # framing the method section exists to correct.
    assert report["tasks_banned"].format(n=len(cells)) not in text, (
        f"the report calls configurations tasks again; {len(cells)} cells over "
        f"{pool} scenarios is not {len(cells)} new tasks"
    )


@_reports
def test_the_report_does_not_invent_a_floor_it_never_measured(report):
    """No do-nothing probe has been run on this substrate.

    The previous substrate's floor was measured, and this guard asserted the
    report stated it. Here the honest property is the inverse: there is no
    floor measurement in `sweep/`, so the report must *say so* rather than
    quoting a number that would look like one. A stated floor that nothing
    produced is precisely the overclaim this module exists to catch -- and this
    repo has already published a floor as a difficulty result once.
    """
    # Two channels, because a floor can arrive by either. A separate probe file
    # is one; the likelier one is a `donothing` arm inside the campaign the
    # runtime already produces, which creates no new file at all. Globbing for
    # the file alone would never fire on that.
    assert not list(_SWEEP.glob("gaia2_donothing*.json")), (
        "a Gaia2 do-nothing probe now exists; this guard must be rewritten to "
        "assert the report states the measured floor, not that it lacks one"
    )
    arms = {k for k in _campaign()["summary"] if k != "by_judge"}
    assert not {a for a in arms if "nothing" in a or "floor" in a}, (
        f"the campaign now measures a floor-shaped arm ({sorted(arms)}); this "
        f"guard must be rewritten to assert the report states it"
    )

    # The phrase must sit on a line that also negates it. Asserting the topic
    # word alone passes a report that says the opposite -- "a do-nothing probe
    # returned a floor of 0.081" contains "do-nothing probe" too, and the whole
    # point of this guard is the difference between those two sentences. Same
    # technique as the control-rate check below: anchor the claim, not the word.
    marker = report["floor_unmeasured"]
    stated = [sent for sent in _sentences(report["path"].read_text())
              if marker in sent and any(n in sent for n in report["floor_negations"])]
    assert stated, (
        f"no line of the report states that the floor is unmeasured: {marker!r} "
        f"has to appear alongside one of {report['floor_negations']}, or the "
        f"guard passes a report that quotes a floor it never measured"
    )


@_reports
def test_the_report_does_not_claim_an_unimplemented_operator_is_shipped(report):
    """The operator table's unshipped/not-built labels must match the code.

    `chain` is defined in `Constraints.allowed_targets` and called by nothing, so
    it is not built, rather than built-but-unshipped. The report had it as the
    latter, which reads as a knob one flag away from working.
    """
    from forge.appworld.partition import Topology

    text = report["path"].read_text()
    assert not any(r["config"].startswith(Topology.CHAIN.value)
                   for r in _campaign()["rows"]), (
        "a chain cell was measured; the report may no longer call it unbuilt"
    )
    assert report["chain_unbuilt"] in text, (
        "chain is unimplemented, not merely unshipped; its handoff has no caller"
    )


@_reports
def test_the_report_does_not_conclude_more_than_the_validity_rule_allows(report):
    """The method section builds the sandwich rule; the results must obey it.

    The rule's third clause refuses to read a constrained score against a
    control that has not itself cleared the floor. On this substrate the control
    succeeded on 2 of 37 scenarios and every constrained arm landed within a
    few hundredths of it, so *no* knob is priced -- and the report must say that
    rather than reading the ordering of four statistically indistinguishable
    means. Reporting "the partition is free" off this campaign is the same
    error, pointed the other way, as publishing a floor as a difficulty result.
    """
    text = report["path"].read_text()
    summary = _campaign()["summary"]
    control = summary["control"]
    # Everything that is not the control and not the judge breakdown, rather
    # than a hardcoded three names: a fifth arm added to the campaign must widen
    # this check, not slip past it while the guard keeps reporting on three.
    constrained = {k: v for k, v in summary.items()
                   if k not in ("control", "by_judge")}
    assert constrained, "the campaign has no constrained arms to compare"

    # The premise of the ban, asserted rather than assumed. If the control ever
    # separates from the constrained arms, the banned sentences below may become
    # *true* and this guard would be enforcing a stale conclusion -- which is
    # the failure the whole module is about, wearing the guard's own clothes.
    spread = max(abs(v["mean_partial_reward"] - control["mean_partial_reward"])
                 for v in constrained.values())
    assert spread < 0.1, (
        f"a constrained arm now differs from the control by {spread:.3f}; the "
        f"bans below no longer follow from the campaign and this test must be "
        f"rewritten, not silenced"
    )

    # Banned phrasings, each one a conclusion the campaign does not support. The
    # first version of this guard listed only one, and the report went on
    # withdrawing the claim in the results and asserting it again in the
    # conclusion -- the same drift the guard exists to stop, three pages later.
    # Test the property, not one sentence.
    #
    # Quoted spans are stripped first, because a substring ban cannot tell an
    # assertion from its own disavowal and the most honest sentence a report can
    # write is the one that names the error in order to reject it. Both reports
    # tripped this on exactly that sentence, and the fix applied was to contort
    # the prose -- a tax on honesty, payable every time the report grows. The
    # module docstring already learned this shape once ("a bare 'liar' substring
    # also matches 'familiar'"): match the claim, not the characters. An author
    # can still assert inside scare quotes, which is unnatural enough to be
    # worth the trade.
    asserted = re.sub(r"``[^']*''|“[^”]*”", "", text)
    for banned in report["overclaims"]:
        assert banned not in asserted, (
            f"the report asserts {banned!r}, which its own acceptance criterion "
            f"rejects: the control succeeded on "
            f"{control['success']}/{control['cells']} scenarios, so no knob "
            f"stacked on it can be priced. To name the claim in order to "
            f"withdraw it, put it in quotes -- quoted spans are exempt."
        )

    # The control's own result, stated in the report, derived here -- and
    # anchored to a sentence that also names the control.
    #
    # `rate in text` is not good enough, and both ways it can fail have already
    # happened in this file. An earlier version asserted a bare fraction and
    # went on passing because an unrelated row carried the same three
    # characters. Requiring the rate in a sentence that also names the arm is
    # what makes this a check rather than a coincidence.
    rate = f"{control['success']}/{control['cells']}"
    stated = [sent for sent in _sentences(text)
              if rate in sent and ("control" in sent or "对照" in sent)]
    assert stated, (
        f"no sentence of the report states the control's result ({rate}) beside the "
        f"control; the acceptance rule's verdict has to appear beside the arm "
        f"that caused it"
    )
    assert report["insufficient"] in text, (
        "the report must say the criterion returned no verdict where it did"
    )


# -- the two guards that would have caught the drift generically -------------


def test_every_evidence_file_the_docs_name_exists():
    """"The file that produced it is named next to it" is a promise (WRITEUP:5).

    A named file that is not there is worse than an unnamed number: it reads as
    checkable and is not. Two of these were deleted by housekeeping commits while
    the prose kept citing them.
    """
    named = set()
    # The .tex reports name their own evidence and were the only documents this
    # scan ever missed -- which is how a whole substrate's citations went
    # unguarded while the four per-claim guards above were being rewritten.
    for doc in (_DOC, _ROOT / "README.md", _TEX_EN, _TEX_ZH,
                _ROOT / "skills" / "constraint-forged-multi-agent-tasks" / "SKILL.md"):
        # LaTeX escapes underscores, so `sweep/gaia2\_full\_campaign.json` would
        # otherwise yield the fragment `_campaign.json`. Un-escape before
        # matching, which is a no-op for the markdown documents.
        text = doc.read_text().replace(r"\_", "_")
        named |= set(re.findall(r"`?(?:sweep/)?(\w+\.json)`?", text))

    on_disk = {p.name for p in _SWEEP.glob("*.json")}
    # "Looks like this repo's evidence" was a hardcoded prefix list, so a name
    # under any substrate the list predated -- gaia2_* among them -- was dropped
    # silently and read as checkable while nothing checked it. Derive the
    # prefixes from what sweep/ actually holds, so a new substrate is covered
    # the moment it writes its first evidence file rather than whenever someone
    # remembers this line.
    #
    # `if head` drops the empty prefix that merge_seeds' `_seed_1.json` outputs
    # would otherwise contribute: a bare "_" matches every name that contains an
    # underscore anywhere, which turns this guard into an unconditional failure.
    prefixes = tuple({head + "_" for head, _, rest in
                      (n.partition("_") for n in on_disk) if head and rest})
    claimed = {n for n in named if n in on_disk or n.startswith(prefixes)}
    missing = sorted(claimed - on_disk)
    assert not missing, f"the docs name evidence files that do not exist: {missing}"


def test_every_section_cross_reference_points_at_a_section_that_exists():
    """§8 was cited for a claim §6 makes; both exist, so nothing complained."""
    text = _DOC.read_text()
    sections = {int(m) for m in re.findall(r"^## (\d+)\.", text, re.M)}
    assert sections, "the write-up has no numbered sections to check"
    cited = {int(m) for m in re.findall(r"§(\d+)", text)}
    dangling = sorted(cited - sections)
    assert not dangling, (
        f"the write-up cites sections that do not exist: {dangling} "
        f"(it has {sorted(sections)})"
    )


def test_the_build_refuses_a_pdf_that_lost_characters():
    """A glyph the font lacks is dropped in silence and the log says so.

    Fandol has no 啰 (U+5570). The sentence shipped as "只是变得更" and stopped,
    the log recorded it, and the build passed -- because the build's own check
    counted overfull boxes and nothing else. A check chosen because it passes is
    the shape of every failure in WRITEUP.md section 7.
    """
    script = (_ROOT / "scripts" / "build_report.sh").read_text()
    assert "Missing character" in script, (
        "build_report.sh does not check for dropped glyphs; XeLaTeX reports them "
        "as a warning and -halt-on-error will not stop"
    )
    assert "Overfull" in script
    # ... and it must actually fail, not just print.
    assert "exit 1" in script, "the build must refuse to copy the PDF, not warn"
