from forge.maf.dimensions.scheduling import DIM
from forge.maf.selfcheck import selfcheck


def test_good_scheduling_instance_passes_all():
    inst = DIM.generate(3, {"n": 7, "k": 3, "trap": True})
    rep = selfcheck(DIM, inst)
    assert rep.ok, rep.checks


def test_trivial_instance_fails_validity():
    inst = DIM.generate(3, {"n": 7, "k": 3, "trap": True})
    trivial = DIM.ablate(inst)  # linear chain: serial == optimal
    rep = selfcheck(DIM, trivial)
    assert not rep.ok
    assert (
        rep.checks["V1_cheaters_lose"] is False
        or rep.checks["V2_discrimination"] is False
    )


def test_c4_robust_to_garbage():
    inst = DIM.generate(1, {"n": 4, "k": 2, "trap": True})
    rep = selfcheck(DIM, inst)
    assert rep.checks["C4_verifier_robust"] is True


def test_report_exposes_cheater_rewards():
    inst = DIM.generate(3, {"n": 7, "k": 3, "trap": True})
    rep = selfcheck(DIM, inst)
    assert set(rep.detail["cheater_rewards"]) == set(DIM.CHEATERS)


class _Undeclared:
    """A dimension that never says what obeying its instruction produces."""
    NAME = DIM.NAME
    CHEATERS = DIM.CHEATERS
    ORACLE = staticmethod(DIM.ORACLE)
    generate = staticmethod(DIM.generate)
    run_policy = staticmethod(DIM.run_policy)
    verify = staticmethod(DIM.verify)
    ablate = staticmethod(DIM.ablate)
    # DICTATION_CHEATER deliberately absent.


class _MisDeclared(_Undeclared):
    """A dimension that names a cheater it does not have."""
    DICTATION_CHEATER = "no_such_policy"


def test_dimension_that_does_not_declare_dictation_is_rejected():
    inst = DIM.generate(2, {"n": 5, "k": 2, "trap": True})
    rep = selfcheck(_Undeclared(), inst)
    assert rep.checks["V4_dictation_declared"] is False
    assert rep.ok is False


def test_dimension_that_names_a_missing_cheater_is_rejected():
    inst = DIM.generate(2, {"n": 5, "k": 2, "trap": True})
    rep = selfcheck(_MisDeclared(), inst)
    assert rep.checks["V4_dictation_declared"] is False
    assert rep.ok is False


def test_scheduling_declares_dictation_and_it_loses():
    inst = DIM.generate(2, {"n": 5, "k": 2, "trap": True})
    rep = selfcheck(DIM, inst)
    assert rep.checks["V4_dictation_declared"] is True
    # V1 already requires this, but pin it explicitly: obeying the instruction
    # must not be enough to win.
    assert rep.detail["cheater_rewards"][DIM.DICTATION_CHEATER] < 0.6
    assert rep.ok is True
