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
