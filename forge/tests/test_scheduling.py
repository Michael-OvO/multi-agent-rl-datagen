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


# --- V4: the declaration must be true, or the gate is theatre -------------


def test_instruction_states_the_procedure_the_declaration_must_obey():
    # DICTATION_CHEATER was declared "serial" on the stated grounds that the
    # instruction "states constraints ... and no procedure". It states one:
    # OUTPUT_CONTRACT ends "...so parallelize independent work across the
    # team." That sentence is the whole basis for deriving the declaration,
    # so pin it: if it ever leaves the contract, DICTATION_CHEATER must be
    # re-derived rather than left pointing at a stale premise.
    assert "parallelize" in DIM.OUTPUT_CONTRACT.lower()


def test_dictation_cheater_is_the_strongest_cheater_not_the_weakest():
    # V4 (selfcheck.py) defines DICTATION_CHEATER as "the best policy
    # achievable by mechanically executing its instruction text". Naming a
    # policy that other cheaters BEAT understates what obeying the
    # instruction gets you -- and what obeying the instruction gets you is
    # the only thing V4 exists to measure.
    #
    # `_serial` is documented "never parallelize": it is the one policy that
    # disobeys the instruction's only procedural sentence, and it scores
    # 0.375-0.5 against greedy_earliest's 0.5. The declaration pointed at
    # the loser and justified it with a claim the contract text contradicts.
    declared = DIM.DICTATION_CHEATER
    assert declared in DIM.CHEATERS
    for difficulty, preset in DIM.DIFFICULTY_PRESETS.items():
        for seed in range(4):
            inst = DIM.generate(seed, preset)
            rewards = {
                name: DIM.verify(inst, DIM.run_policy(inst, pol)).reward
                for name, pol in DIM.CHEATERS.items()
            }
            assert rewards[declared] >= max(rewards.values()), (
                difficulty,
                seed,
                rewards,
            )
