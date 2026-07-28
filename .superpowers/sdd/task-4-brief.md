### Task 4: Dictation gate (G2)

The cheater panel has no policy that mechanically executes the instruction. That hole is why `theory-of-mind` passed every gate while both models scored `asks == q_opt` on 12/12 runs — the instruction stated the optimal algorithm, and no cheater tested for it.

This gate needs no new machinery: `selfcheck` already requires every entry in `CHEATERS` to score below `tau` (V1, `forge/maf/selfcheck.py:65`). The gate only has to force each dimension to *name* which cheater plays the dictation role; V1 then scores it.

**The gate is a declaration, not a new policy.** `parallel-scheduling`'s instruction states constraints (respect dependencies, match skills) and no procedure, so the best policy achievable by mechanically following it — honour the constraints, do not optimise — is exactly the existing `_serial` (`forge/maf/dimensions/scheduling.py:121-129`). Adding a `_dictation` function would duplicate `_serial` byte for byte and prove nothing. So `DICTATION_CHEATER` is a pointer into `CHEATERS`, and the intellectual work the gate demands is answering "what does mechanically obeying my instruction produce?" — the question `theory-of-mind` was never forced to answer, and which would have exposed `asks == q_opt` immediately.

**Files:**
- Modify: `forge/maf/selfcheck.py:25-78`
- Modify: `forge/maf/dimensions/scheduling.py:159` (add `DICTATION_CHEATER`), and the `_Scheduling` class body
- Test: `forge/tests/test_selfcheck.py`

**Interfaces:**
- Consumes: `dim.CHEATERS: dict[str, Policy]`, `selfcheck(dim, instance, tau=0.6, delta=0.4, eps=0.05) -> SelfcheckReport` (existing).
- Produces: a new check key `V4_dictation_declared` in `SelfcheckReport.checks`, and a required dimension attribute `DICTATION_CHEATER: str` naming a key of `CHEATERS`. Plan 2's `belief-tracking` must set it.

- [ ] **Step 1: Write the failing test**

Add to `forge/tests/test_selfcheck.py`:

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest forge/tests/test_selfcheck.py -v`

Expected: FAIL with `KeyError: 'V4_dictation_declared'`.

- [ ] **Step 3: Add the gate to selfcheck**

In `forge/maf/selfcheck.py`, insert after the `V3_ablation` block (after line 76), before the `return`:

```python
    # V4: the dimension must name which cheater is the best policy achievable by
    # mechanically executing its instruction text. V1 then requires that cheater
    # to score below tau. A dimension whose instruction states its own optimal
    # algorithm measures instruction-following, not the target skill --
    # theory-of-mind scored asks == q_opt on 12/12 sweep runs for exactly that
    # reason, and no cheater in its panel tested for it.
    dictation = getattr(dim, "DICTATION_CHEATER", None)
    checks["V4_dictation_declared"] = dictation in dim.CHEATERS
    detail["dictation_cheater"] = dictation
```

Also update the module docstring (line 5) to name the third property:

```python
"""The CLEAN/VALID gate battery (DESIGN.md §4.3).

Run in-process at generation time -- no Docker, no LLM tokens. An instance ships
only if every check passes. CLEAN = the reward has no noise; VALID = the reward
gap is caused by the target skill, and not by the instruction handing the agent
its own optimal algorithm (V4).
"""
```

- [ ] **Step 4: Declare scheduling's dictation cheater**

Do **not** write a new policy. `_serial` (`forge/maf/dimensions/scheduling.py:121-129`) already is scheduling's dictation policy: it honours every constraint the instruction states — dependency order via `_topo_order`, skill match via `_first_capable` — and optimises nothing, because the instruction describes no procedure to optimise with. A separate `_dictation` would be a byte-for-byte copy of it.

Add the declaration next to `CHEATERS` (line 159):

```python
CHEATERS = {"serial": _serial, "greedy_earliest": _greedy_earliest}

# V4: what does mechanically obeying our instruction produce? The instruction
# states constraints (dependency order, skill match) and no procedure, so
# obeying it literally *is* _serial -- valid, unoptimised, and 0.5 at best.
DICTATION_CHEATER = "serial"
```

Expose it on the dimension object. In the `_Scheduling` class body, alongside `CHEATERS = CHEATERS`:

```python
    DICTATION_CHEATER = DICTATION_CHEATER
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest forge/tests/test_selfcheck.py forge/tests/test_scheduling.py -v`

Expected: PASS. `_serial` never parallelises, so its makespan is the sum of all durations; `test_serial_cheater_is_suboptimal_on_trap` (`forge/tests/test_scheduling.py:20`) already pins it below the oracle, and the sweep measured it at 0.375–0.5 — under `tau=0.6`.

- [ ] **Step 6: Commit**

```bash
git add forge/maf/selfcheck.py forge/maf/dimensions/scheduling.py forge/tests/test_selfcheck.py
git commit -m "feat(g2): require every dimension to name its dictation cheater

V4 asserts DICTATION_CHEATER names a real entry in CHEATERS -- the best
policy achievable by mechanically executing the instruction text. V1 already
requires every cheater to score below tau, so V4 adds no scoring machinery
and no duplicate policy: scheduling points at the existing _serial, which is
already exactly 'obey the constraints, optimise nothing'.

This is the gate theory-of-mind needed and never had. Its instruction named
each topic's entry witness and said to follow referrals, and doing exactly
that costs exactly q_opt -- both models hit asks == q_opt on 12/12 runs.
Forcing the author to answer 'what does obeying my instruction produce?'
would have exposed it at generation time, with no model runs."
```

---

