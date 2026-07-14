from forge.maf.dimensions.theory_of_mind import DIM
from forge.maf.selfcheck import selfcheck

MED = {"suspects": 5, "referral_depth": 2}


def test_unique_solution():
    for s in range(20):
        inst = DIM.generate(s, MED)
        assert DIM.unique_ground_truth(inst)


def test_oracle_solves_within_budget():
    for s in range(20):
        inst = DIM.generate(s, MED)
        r = DIM.verify(inst, DIM.run_policy(inst, DIM.ORACLE))
        assert r.reward == 1.0, (s, r.subscores)


def test_info_dump_cannot_win_under_budget():
    for s in range(10):
        inst = DIM.generate(s, MED)
        r = DIM.verify(inst, DIM.run_policy(inst, DIM.CHEATERS["info_dump"]))
        assert r.reward < 0.6, (s, r.reward)


def test_no_referral_fails():
    inst = DIM.generate(0, MED)
    r = DIM.verify(inst, DIM.run_policy(inst, DIM.CHEATERS["no_referral"]))
    assert r.gate == 0


def test_selfcheck_passes():
    for s in range(5):
        inst = DIM.generate(s, MED)
        assert selfcheck(DIM, inst).ok, selfcheck(DIM, inst).checks


def test_ablation_direct_read_wins():
    inst = DIM.generate(2, MED)
    twin = DIM.ablate(inst)
    r = DIM.verify(twin, DIM.run_policy(twin, DIM.CHEATERS["no_referral"]))
    assert r.reward >= 0.95


def test_generation_is_deterministic():
    assert DIM.generate(3, MED) == DIM.generate(3, MED)
