# Task 4 Report: Dictation gate (V4)

## Summary

Added V4 to the selfcheck gate battery: every dimension must declare
`DICTATION_CHEATER`, a string naming an entry in its own `CHEATERS` dict —
the answer to "what does mechanically obeying my instruction produce?". V1
(already existing) then requires that named cheater to score below `tau`.
V4 adds no new scoring machinery and no new policy; it only forces the
dimension author to point at whichever existing cheater plays that role, and
lets V1 grade it.

Commit: `b3e98338728384b252b87d45217f6f0a6cbef1a3` on branch
`fix/isolation-and-gates`.

## Changes

1. **`forge/maf/selfcheck.py`**
   - Module docstring: VALID now also names "not caused by the instruction
     handing the agent its own optimal algorithm (V4)".
   - After the `V3_ablation` block, added:
     ```python
     dictation = getattr(dim, "DICTATION_CHEATER", None)
     checks["V4_dictation_declared"] = dictation in dim.CHEATERS
     detail["dictation_cheater"] = dictation
     ```
     `getattr(..., None)` means a dimension missing the attribute gets
     `None`, and `None in dim.CHEATERS` is `False` (CHEATERS keys are
     strings) — no exception, just a failed check. `ok = all(checks.values())`
     already existed, so this key is blocking with no further changes needed.

2. **`forge/maf/dimensions/scheduling.py`**
   - Added, next to `CHEATERS` (module level):
     ```python
     DICTATION_CHEATER = "serial"
     ```
     with a comment explaining that the instruction states constraints
     (dependency order, skill match) and no procedure, so obeying it
     literally *is* `_serial` — no new function was written; `_serial`
     (lines 121-129, unchanged) already is that policy.
   - Exposed it on the `_Scheduling` class body: `DICTATION_CHEATER =
     DICTATION_CHEATER`, so it's reachable as `DIM.DICTATION_CHEATER`.

3. **`forge/tests/test_selfcheck.py`** — added the four tests from the brief
   verbatim: `_Undeclared` / `_MisDeclared` fixture classes built off
   `parallel-scheduling`'s `DIM`, plus
   `test_dimension_that_does_not_declare_dictation_is_rejected`,
   `test_dimension_that_names_a_missing_cheater_is_rejected`, and
   `test_scheduling_declares_dictation_and_it_loses`.

4. **`forge/tests/test_theory_of_mind.py`** and
   **`forge/tests/test_failure_recovery.py`** — see "Ambiguity resolution"
   below; each `test_selfcheck_passes` is now marked
   `@pytest.mark.xfail(strict=True, reason=...)`.

## What V4 does to each of the three dimensions

- **`parallel-scheduling`**: passes. `DICTATION_CHEATER = "serial"` is
  declared and real. `_serial` never parallelizes, so its makespan is the
  sum of all durations on the constructed trap instances — the recorded
  sweep measured it at 0.375–0.5, under `tau = 0.6`. Confirmed by
  `test_scheduling_declares_dictation_and_it_loses`
  (`rep.detail["cheater_rewards"]["serial"] < 0.6`) and by
  `test_good_scheduling_instance_passes_all` continuing to pass.

- **`theory-of-mind`**: fails, by design. It has no `DICTATION_CHEATER`
  because none of its cheaters (`info_dump`, `random_target`, `no_referral`)
  is "mechanically obey the instruction" — the instruction *itself* states
  the optimal algorithm (name each topic's entry witness, follow referral
  chains), so the policy that literally obeys it *is* the oracle, not a
  cheater. There is no losing policy to point at. `V4_dictation_declared`
  is `False` for this dimension unconditionally, so `selfcheck(DIM,
  inst).ok` is now always `False`.

- **`failure-recovery`**: fails, for the same structural reason. Its own
  docstring states the "canonical recovery strategy" is exactly the
  optimum (topological task order, try rostered workers in sorted order,
  move on after a failure) — mechanically following the instruction is the
  oracle here too, and none of its cheaters (`static_plan`, `retry_same`,
  `brute_force`) represents "obey the instruction, get nothing extra."
  `V4_dictation_declared` is `False` unconditionally.

## Test results

Full suite: `.venv/bin/python -m pytest forge/tests/` → **60 passed, 2
xfailed** (0 failed).

- `forge/tests/test_selfcheck.py` and `forge/tests/test_scheduling.py`: all
  pass, including the 4 new V4 tests, exactly as the brief predicted.
- `forge/tests/test_theory_of_mind.py::test_selfcheck_passes` and
  `forge/tests/test_failure_recovery.py::test_selfcheck_passes`: now
  `xfail(strict=True)`. Before marking them, I ran them unmodified to
  confirm the failure mode matches the brief's prediction exactly —
  `rep.checks["V4_dictation_declared"]` is `False` and every other check
  (`C1`–`C5`, `V1`–`V3`) is `True`, so V4 alone is what turns `rep.ok` from
  `True` to `False`. I did not add `DICTATION_CHEATER` to either dimension
  and did not touch their production code — only the two test files were
  edited, each adding an `xfail` decorator whose `reason` names V4 and
  Task 6's quarantine.

No other test files reference these two `selfcheck_passes` tests or depend
on their prior "pass" status.

## Surprising / worth flagging

**V4 doesn't just fail two unit tests — it fully disables generation for
these two dimensions right now.** `forge/forge_cli.py` and
`scripts/eval_sweep_gen.py` both call `selfcheck` as the shipping gate at
generation time. I ran the actual CLI to check the blast radius beyond the
test suite:

```
$ .venv/bin/python -m forge.forge_cli gen --dim theory-of-mind --seed 0 --n 3 --difficulty medium --out <tmp>
{"dim": "theory-of-mind", "requested": 3, "shipped": 0,
 "rejected": [{"seed": 0, "failed": ["V4_dictation_declared"]}, ...]}

$ .venv/bin/python -m forge.forge_cli gen --dim failure-recovery --seed 0 --n 3 --difficulty medium --out <tmp>
{"dim": "failure-recovery", "requested": 3, "shipped": 0,
 "rejected": [{"seed": 0, "failed": ["V4_dictation_declared"]}, ...]}

$ .venv/bin/python -m forge.forge_cli gen --dim parallel-scheduling --seed 0 --n 3 --difficulty medium --out <tmp>
{"dim": "parallel-scheduling", "requested": 3, "shipped": 3, "rejected": []}
```

So as of this commit, `forge_cli gen` and `scripts/eval_sweep_gen.py` will
ship **zero** instances for `theory-of-mind` or `failure-recovery` at any
seed or difficulty, every rejection being `V4_dictation_declared` alone (all
other checks pass). `parallel-scheduling` is unaffected and ships normally.
This is the gate working exactly as intended per the brief — these two
dimensions are degenerate and Task 6 is expected to quarantine them — but it
is a live, immediate effect on the generation pipeline today, not just a
future concern, and whoever picks up Task 6 should know these two
dimensions are already fully blocked rather than merely "at risk."

I did not modify `forge_cli.py`, `scripts/eval_sweep_gen.py`, or either
dimension's production code to work around this — per the brief's explicit
instruction not to fabricate a `DICTATION_CHEATER` for dimensions about to
be quarantined.
