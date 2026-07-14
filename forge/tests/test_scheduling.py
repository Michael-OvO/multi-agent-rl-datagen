from forge.maf.dimensions.scheduling import DIM


def test_oracle_scores_one_across_seeds():
    for seed in range(20):
        inst = DIM.generate(seed, {"n": 6, "k": 3, "trap": True})
        sub = DIM.run_policy(inst, DIM.ORACLE)
        assert DIM.verify(inst, sub).reward == 1.0, seed


def test_verify_rejects_dependency_violation():
    inst = DIM.generate(1, {"n": 4, "k": 2, "trap": False})
    bad = DIM.run_policy(inst, DIM.ORACLE)
    # force a dependent task to start at 0, violating its dependency
    dependent = next(e for e in bad if inst["subtasks"][e["subtask"]]["deps"])
    dependent["start"] = 0
    assert DIM.verify(inst, bad).gate == 0


def test_serial_cheater_is_suboptimal_on_trap():
    inst = DIM.generate(3, {"n": 6, "k": 3, "trap": True})
    r = DIM.verify(inst, DIM.run_policy(inst, DIM.CHEATERS["serial"]))
    assert r.gate == 1 and r.reward < 1.0


def test_greedy_cheater_is_suboptimal_on_trap():
    inst = DIM.generate(3, {"n": 6, "k": 3, "trap": True})
    r = DIM.verify(inst, DIM.run_policy(inst, DIM.CHEATERS["greedy_earliest"]))
    assert r.gate == 1 and r.reward < 0.6


def test_ablation_makes_serial_optimal():
    inst = DIM.generate(3, {"n": 6, "k": 3, "trap": True})
    twin = DIM.ablate(inst)
    r = DIM.verify(twin, DIM.run_policy(twin, DIM.CHEATERS["serial"]))
    assert r.reward >= 0.95


def test_generation_is_deterministic():
    assert DIM.generate(7, {"n": 6, "k": 3, "trap": True}) == DIM.generate(
        7, {"n": 6, "k": 3, "trap": True}
    )


def test_unique_ground_truth_holds():
    inst = DIM.generate(5, {"n": 7, "k": 3, "trap": True})
    assert DIM.unique_ground_truth(inst)
