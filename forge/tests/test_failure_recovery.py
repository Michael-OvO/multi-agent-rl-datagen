import pytest

from forge.maf.dimensions.failure_recovery import DIM
from forge.maf.selfcheck import selfcheck

MED = {"n": 5, "workers": 3, "fail_rate": 0.35}


def test_oracle_completes_and_scores_one():
    for s in range(20):
        inst = DIM.generate(s, MED)
        r = DIM.verify(inst, DIM.run_policy(inst, DIM.ORACLE))
        assert r.reward == 1.0, (s, r.subscores)


def test_static_plan_fails_when_failures_present():
    inst = DIM.generate(0, {"n": 5, "workers": 3, "fail_rate": 0.4})
    r = DIM.verify(inst, DIM.run_policy(inst, DIM.CHEATERS["static_plan"]))
    assert r.reward < 0.6


def test_brute_force_exhausts_budget():
    inst = DIM.generate(0, {"n": 5, "workers": 3, "fail_rate": 0.4})
    r = DIM.verify(inst, DIM.run_policy(inst, DIM.CHEATERS["brute_force"]))
    assert r.reward < 0.6


@pytest.mark.xfail(
    reason="V4 (selfcheck.py) requires DICTATION_CHEATER: failure-recovery's "
    "instruction describes the canonical recovery strategy itself (topological "
    "order, try rostered workers in sorted order, move on after a failure), "
    "and mechanically following it literally reaches the optimum -- so no "
    "cheater in CHEATERS can play the dictation role. This dimension is "
    "degenerate and is quarantined by Task 6, not fixed here.",
    strict=True,
)
def test_selfcheck_passes():
    inst = DIM.generate(1, MED)
    rep = selfcheck(DIM, inst)
    assert rep.ok, rep.checks


def test_ablation_static_plan_wins():
    inst = DIM.generate(1, MED)
    twin = DIM.ablate(inst)
    r = DIM.verify(twin, DIM.run_policy(twin, DIM.CHEATERS["static_plan"]))
    assert r.reward >= 0.95


def test_generation_is_deterministic():
    assert DIM.generate(3, MED) == DIM.generate(3, MED)
