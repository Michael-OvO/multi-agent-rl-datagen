"""The sandwich rule must hold at its edges, and must bind the shipped sweep.

Every boundary here is one this repo got wrong in prose before it was code:
`0.333` was published as difficulty when it was the floor, and a config that
ties its control was reported as an effect.

Several tests below exist because a mutation survived an earlier version of this
file: a constant `seeds = 1`, a `rate` that always returned 0.0, a `measured`
that always returned False, and `startswith` in place of a segment match all
passed 16 green tests. A test that a constant satisfies guards nothing.
"""

import json
from pathlib import Path

import pytest

from forge.appworld.validity import (
    SEEDS_FOR_YIELD,
    Verdict,
    control_by_task,
    is_control,
    is_measurement,
    judge,
    judge_cell,
    judge_cells,
    judge_rows,
    yield_by_config,
)

_ROOT = Path(__file__).resolve().parents[2]
_SWEEP = _ROOT / "sweep"

FLOOR = 0.333


def _row(task, config, partial, **kw):
    return {"task_id": task, "config": config, "partial": partial, "ran": True, **kw}


# -- the rule, at its edges --------------------------------------------------


@pytest.mark.parametrize(
    "score,expected",
    [
        (0.833, Verdict.VALID),  # strictly inside: the only usable cell
        (0.334, Verdict.VALID),  # just above the floor still carries signal
        (0.999, Verdict.VALID),  # just below the control still bit
        (FLOOR, Verdict.DEGENERATE),  # *at* the floor is not above it
        (0.2, Verdict.DEGENERATE),  # below the floor: worse than doing nothing
        (1.0, Verdict.NO_BITE),  # ties the control: the knob changed nothing
        (1.1, Verdict.NO_BITE),
    ],
)
def test_the_sandwich_is_strict_at_both_ends(score, expected):
    assert judge(score, control=1.0, floor=FLOOR) is expected


def test_a_control_on_the_floor_makes_every_knob_unmeasurable():
    """A knob's effect cannot be read against a control that already failed.

    Without this branch a broken base task reads as a knob that bites: score
    0.333 against control 0.333 would score DEGENERATE, blaming the partition
    for a task nobody can solve.
    """
    assert judge(FLOOR, control=FLOOR, floor=FLOOR) is Verdict.CONTROL_FAILED
    assert judge(0.5, control=FLOOR, floor=FLOOR) is Verdict.CONTROL_FAILED


def test_the_control_is_matched_on_a_segment_not_a_prefix():
    """`startswith` passes every other test in this file; only this catches it."""
    assert is_control("open-docs-binf")
    assert not is_control("star-names-binf")
    assert not is_control("openish-docs-binf")  # prefix, not segment


@pytest.mark.parametrize(
    "row,expected",
    [
        ({"partial": 1.0, "ran": True, "error": None}, True),
        ({"partial": 1.0, "ran": False, "error": None}, False),  # never ran
        ({"partial": 1.0, "ran": True, "error": "429"}, False),  # crashed
        ({"partial": None, "ran": True, "error": None}, False),  # never scored
        ({"partial": 1.0}, True),  # `ran` absent means legacy row that ran
    ],
)
def test_only_real_measurements_are_scored(row, expected):
    """A call that 400'd reports the untouched world's score, same as failure."""
    assert is_measurement(row) is expected


def test_a_rollout_that_never_ran_is_excluded_rather_than_scored():
    rows = [
        _row("t", "open-docs-binf", 1.0),
        _row("t", "star-names-binf", 0.333, ran=False),
    ]
    assert judge_rows(rows, FLOOR) == []


def test_a_rollout_that_errored_is_excluded_even_though_it_ran():
    rows = [
        _row("t", "open-docs-binf", 1.0),
        _row("t", "star-names-binf", 0.333, error="RateLimit"),
    ]
    assert judge_rows(rows, FLOOR) == []


# -- the control lookup, which every other verdict depends on ----------------


def test_the_control_is_the_mean_of_its_rollouts_not_whichever_came_last():
    """At >1 seed a dict keyed by task keeps the last row, so order decides.

    This is the multi-seed regime the module is written for, and the bug it
    shipped with: the same rows in a different file order gave opposite
    verdicts.
    """
    rows = [
        _row("t", "open-docs-binf", 1.0),
        _row("t", "open-docs-binf", 0.4),
        _row("t", "star-docs-binf", 0.7),
    ]
    assert control_by_task(rows)["t"] == pytest.approx(0.7)
    # ... and reversing the file must not change a single verdict.
    assert control_by_task(list(reversed(rows)))["t"] == pytest.approx(0.7)
    assert [j.verdict for j in judge_rows(rows, FLOOR)] == [
        j.verdict for j in judge_rows(list(reversed(rows)), FLOOR)
    ]


def test_a_control_that_never_ran_is_not_trusted_as_the_ceiling():
    """The worst row to trust: it defines every other verdict on its task."""
    rows = [
        _row("t", "open-docs-binf", 1.0),
        _row("t", "open-docs-binf", 0.333, ran=False),
    ]
    assert control_by_task(rows)["t"] == pytest.approx(1.0)


def test_a_task_with_no_control_that_ran_is_refused_by_name():
    """Silently dropping it would shrink a yield's denominator without saying so."""
    rows = [
        _row("t9", "open-docs-binf", 1.0, ran=False),
        _row("t9", "star-docs-binf", 0.5),
    ]
    with pytest.raises(ValueError, match="t9"):
        judge_rows(rows, FLOOR)


# -- yield -------------------------------------------------------------------


def test_the_weakest_cell_governs_the_seed_count():
    """An average would certify a measured yield off one 9-seed task.

    `seeds = len(rows) // len(tasks)` returns 5 here and calls it measured,
    while task `b` has a single draw. That is the guard defeating itself.
    """
    rows = [_row("a", "open-docs-binf", 1.0), _row("b", "open-docs-binf", 1.0)]
    rows += [_row("a", "star-docs-binf", 0.5) for _ in range(9)]
    rows += [_row("b", "star-docs-binf", 0.5)]

    y = yield_by_config(judge_cells(rows, FLOOR))["star-docs-binf"]
    assert y.seeds == 1, "the 1-seed cell governs, not the 10/2 average"
    assert not y.measured


def test_enough_seeds_in_every_cell_makes_the_rate_a_measured_yield():
    """The True direction of `measured`; `return False` passes without it."""
    rows = [_row("a", "open-docs-binf", 1.0)]
    rows += [_row("a", "star-docs-binf", 0.5) for _ in range(SEEDS_FOR_YIELD)]

    y = yield_by_config(judge_cells(rows, FLOOR))["star-docs-binf"]
    assert y.seeds == SEEDS_FOR_YIELD
    assert y.measured


def test_the_rate_is_the_usable_fraction():
    """`rate` had no test at all; `return 0.0` passed the whole file."""
    rows = [_row(t, "open-docs-binf", 1.0) for t in "abcd"]
    rows += [_row("a", "star-docs-binf", 0.5)]  # valid
    rows += [_row("b", "star-docs-binf", 0.5)]  # valid
    rows += [_row("c", "star-docs-binf", 1.0)]  # no-bite
    rows += [_row("d", "star-docs-binf", 0.1)]  # degenerate

    y = yield_by_config(judge_cells(rows, FLOOR))["star-docs-binf"]
    assert (y.valid, y.total) == (2, 4)
    assert y.rate == pytest.approx(0.5)


def test_an_empty_config_rates_zero_rather_than_dividing_by_zero():
    assert yield_by_config([]) == {}


def test_cells_whose_control_failed_are_not_counted_against_the_knob():
    """Otherwise a broken base task is written up as a 67% knob failure."""
    rows = [
        _row("ok", "open-docs-binf", 1.0),
        _row("ok", "star-docs-binf", 0.5),  # valid
        _row("broke1", "open-docs-binf", 0.333),  # control on the floor
        _row("broke1", "star-docs-binf", 0.333),
        _row("broke2", "open-docs-binf", 0.333),
        _row("broke2", "star-docs-binf", 0.333),
    ]
    y = yield_by_config(judge_cells(rows, FLOOR))["star-docs-binf"]
    assert (y.valid, y.total, y.unmeasurable) == (1, 1, 2)
    assert y.rate == pytest.approx(1.0), "1/1 measurable, not 1/3"


# -- the cell rule: what replicates buy you ---------------------------------


def test_five_identical_replicates_have_no_gradient_however_good_the_score():
    """The v1 failure, in the shape a sandwich alone cannot see.

    0.833 sits comfortably inside `floor < score < control`, so every per-rollout
    verdict says VALID -- five times. But five identical scores give GRPO nothing
    to subtract: zero variance, zero advantage, zero gradient. That is
    `theory-of-mind` scoring 1.0 on 12 of 12 with a different number on it.
    """
    assert judge_cell([0.833] * 5, control=1.0, floor=FLOOR) is Verdict.NO_VARIANCE
    # ... and the per-rollout rule really would have called every one of them fine
    assert all(judge(s, 1.0, FLOOR) is Verdict.VALID for s in [0.833] * 5)


def test_a_cell_is_usable_when_its_replicates_actually_spread():
    """Sometimes solved, sometimes not: the thing you can learn from."""
    assert judge_cell([1.0, 1.0, 0.833, 0.333, 1.0], 1.0, FLOOR) is Verdict.VALID


def test_one_replicate_is_never_called_zero_variance():
    """A single point has no variance by construction; that is ignorance, not a
    verdict. Calling it NO_VARIANCE would condemn every 1-seed sweep."""
    assert judge_cell([0.833], control=1.0, floor=FLOOR) is Verdict.VALID


def test_a_cell_that_never_clears_the_floor_is_degenerate_even_with_spread():
    """Variance between bad and worse is not signal about the task."""
    assert judge_cell([0.333, 0.167, 0.333], 1.0, FLOOR) is Verdict.DEGENERATE


def test_a_cell_that_always_ties_the_ceiling_never_bit():
    assert judge_cell([1.0, 1.0, 1.0], 1.0, FLOOR) is Verdict.NO_BITE


def test_the_yield_counts_cells_not_rollouts():
    """The unit of RL data is the prompt. Counting rollouts answers a different
    question -- "how often does a rollout land in the band" -- and at K seeds it
    silently multiplies the denominator by K."""
    rows = [_row("a", "open-docs-binf", 1.0), _row("b", "open-docs-binf", 1.0)]
    rows += [_row("a", "star-docs-binf", s) for s in (1.0, 0.833, 1.0)]  # spread -> valid
    rows += [_row("b", "star-docs-binf", s) for s in (0.333, 0.333, 0.333)]  # floor

    y = yield_by_config(judge_cells(rows, FLOOR))["star-docs-binf"]
    assert (y.valid, y.total) == (1, 2), "two cells, one usable -- not six rollouts"


# -- the rule, against the sweep it was written for --------------------------


def _sweep():
    return json.loads((_SWEEP / "appworld_knobs_v5.json").read_text())


def _floor():
    rows = json.loads((_SWEEP / "appworld_donothing.json").read_text())
    floors = {r["partial"] for r in rows}
    assert len(floors) == 1, f"the floor is not a single number: {floors}"
    return floors.pop()


def test_the_floor_the_rule_uses_is_the_floor_that_was_measured():
    assert _floor() == FLOOR


def test_every_task_in_the_sweep_has_a_control_to_be_read_against():
    rows = _sweep()
    assert {r["task_id"] for r in rows} == set(control_by_task(rows))


def test_the_shipped_configs_yield_five_usable_cells_in_six():
    """The measurement that motivated this module, at the seed count it asks for.

    At one seed this read 1 of 6, and that number was never a yield -- it was
    one draw per cell, which `SEEDS_FOR_YIELD` exists to refuse. star-docs tied
    the control on two of three tasks and was called NO_BITE; at five seeds
    those same cells spread (1.000 1.000 0.833 0.667 0.667), `min < control`,
    and they are VALID. The variance was always there. One draw could not see
    it, and the write-up spent two versions explaining a number that was an
    artefact of the sample size.

    So this is the rule vindicating itself rather than a better result arriving:
    nothing about the tasks changed between 1 seed and 5.

    This asserts the arithmetic, not that the arithmetic is good news. If a
    later sweep moves these, update the numbers -- after checking the harness.
    """
    ys = yield_by_config(judge_cells(_sweep(), _floor()))

    shipped = {"star-docs-binf", "star-names-binf"}
    assert shipped <= set(ys), f"the shipped configs are not in the sweep: {set(ys)}"
    assert (ys["star-docs-binf"].valid, ys["star-docs-binf"].total) == (3, 3)
    assert (ys["star-names-binf"].valid, ys["star-names-binf"].total) == (2, 3)

    valid = sum(ys[c].valid for c in shipped)
    total = sum(ys[c].total for c in shipped)
    assert (valid, total) == (5, 6)


def test_star_names_still_has_one_cell_that_never_leaves_the_floor():
    """Guards the claim the write-up may not make: that star-names is a gradient.

    Its yield improves to 2/3 at five seeds, and the reason it is not 3/3 is
    unchanged -- 2a163ab_2 scores 0.167 on all five replicates, below the
    do-nothing floor, because the Main reports failure in prose and `assert
    answers match` wants the action answer. That is the protocol incentive in
    WRITEUP.md section 5, not difficulty, and seeds do not launder it.
    """
    cells = [c for c in judge_cells(_sweep(), _floor())
             if c.config == "star-names-binf"]
    floored = [c for c in cells if c.verdict is Verdict.DEGENERATE]
    assert len(floored) == 1, f"expected one floored cell, got {[c.task_id for c in floored]}"
    assert set(floored[0].scores) == {0.167}, (
        "the floored cell is no longer uniformly sub-floor; re-read section 5"
    )


def test_a_run_can_score_below_the_do_nothing_floor_and_still_be_judged():
    """The floor is not a lower bound, and the rule must not assume it is.

    An agent that fails and says so in prose scores 1/6 = 0.167; the do-nothing
    baseline, which submits the action answer, scores 2/6 = 0.333. Reporting
    failure costs more than silence. `judge` handles it because the test is
    `score <= floor`, not `score == floor` -- but the docs called 0.333 a lower
    bound, and it is not.
    """
    below = [j for j in judge_rows(_sweep(), _floor()) if j.score < _floor()]
    assert below, "no sub-floor cells; if the sweep changed, re-check this claim"
    assert all(j.verdict is Verdict.DEGENERATE for j in below)


def test_the_unshipped_chain_config_is_degenerate_everywhere():
    """chain was never shipped because its sub-to-sub handoff was never built."""
    js = [j for j in judge_rows(_sweep(), _floor()) if j.config.startswith("chain")]
    assert js, "the sweep no longer contains chain; drop this test with it"
    assert all(j.verdict is Verdict.DEGENERATE for j in js)


def test_the_shipped_configs_carry_enough_seeds_to_call_their_rate_a_yield():
    """This test used to assert the opposite, and that was the point of it.

    It read `all(y.seeds == 1)` / `not any(y.measured)` -- a tripwire pinning
    the sweep to one draw per cell, so that the day seeds arrived it would fail
    and force the prose to move with them. It fired. The shipped configs are at
    five replicates now, `SEEDS_FOR_YIELD` is satisfied, and `cli judge` prints
    YIELD instead of "observed only".

    chain is deliberately excluded: it stopped at two seeds because it was never
    implemented, and `Yield.seeds` reports it honestly rather than averaging it
    away. A config nobody finished is not a config whose yield is unmeasured.
    """
    ys = yield_by_config(judge_cells(_sweep(), _floor()))

    for config in ("star-docs-binf", "star-names-binf"):
        assert ys[config].seeds >= SEEDS_FOR_YIELD, (
            f"{config} has {ys[config].seeds} replicates in its weakest cell; "
            f"below {SEEDS_FOR_YIELD} its rate is an observation, not a yield"
        )
        assert ys[config].measured

    assert not ys["chain-names-binf"].measured, (
        "chain reached five seeds; either it was implemented or the sweep is "
        "spending rollouts on a config the repo calls unbuilt"
    )


def test_at_one_replicate_the_cell_rule_and_the_row_rule_agree():
    """`cli judge` prints both tables. If they can disagree, one of them lies.

    The rules are separate because they answer different questions -- is this
    rollout in the band, is this prompt trainable -- and at a single replicate
    those questions collapse into one. Exhaustive over the score/control lattice
    the oracle can actually produce (N/6 for N in 0..6, plus the boundaries).
    """
    grid = [round(n / 6, 3) for n in range(7)] + [0.0, 1.0, 1.1]
    for score in grid:
        for control in grid:
            assert judge(score, control, FLOOR) is judge_cell([score], control, FLOOR), (
                f"score={score} control={control}: the per-rollout table and the "
                f"per-cell table would print different verdicts for the same row"
            )
