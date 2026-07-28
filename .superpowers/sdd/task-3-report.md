# Task 3 Report: Relocate the dimension module out of the agent image

## Summary

Implemented the brief's Steps 1-7 verbatim, plus the three carried-over
context items (maf_core.py removal, harbor.py module docstring, DESIGN.md
diagram), plus two test fixes made necessary by the relocation that were
outside the brief's explicit file list but are direct, unavoidable
consequences of it (see "Tests touched beyond the brief" below).

## Files changed

- `forge/maf/harbor.py` — `write_task` now creates `tests/lib` (not
  `environment/lib`) and calls `_copy_runtime(dim, task_dir/"tests"/"lib",
  include_cli=dim.INTERACTIVE)`. `_write_static`'s Dockerfile no longer emits
  `COPY lib /app/lib` — only `COPY task.json /app/task.json`. `_copy_runtime`
  takes an explicit `include_cli` parameter (replacing the `getattr(dim,
  "INTERACTIVE", False)` check) and `mkdir(parents=True, exist_ok=True)`s its
  target since `tests/lib` isn't pre-created by `write_task`'s loop the way
  `environment/lib` used to be implicitly nested under `environment`.
  Module docstring rewritten (see below). `_write_interactive` was
  deliberately left untouched — its Dockerfile still does `COPY lib
  /app/lib`, which will now fail to build for interactive dimensions since
  nothing populates `environment/lib` anymore. Per the brief's ambiguity
  resolution, this breakage is expected and owned by Task 6.
- `forge/maf/runtime/verify_entry.py` — `sys.path.insert(0, "/app/lib")` →
  `sys.path.insert(0, "/tests/lib")`.
- `forge/tests/test_harbor.py` — replaced `test_public_files_hide_ground_truth`
  with `test_agent_image_hides_ground_truth_and_grader` (asserts `audit(d) ==
  []`) and `test_dimension_module_ships_to_tests_not_environment` (asserts
  `tests/lib/maf_dim.py` exists and `environment/lib` does not), exactly per
  Step 1. Also updated `test_write_task_produces_valid_tree` and
  `test_copied_module_has_no_package_imports`, which asserted
  `environment/lib/maf_{core,dim}.py` paths — these are not in the brief's
  file list but were asserting the exact old (now-removed) location, so they
  were failing hard after Step 3 and needed the same path fix, not a scope
  change to their intent.
- `forge/tests/test_leak_audit.py` — dropped `@pytest.mark.xfail(...)` (and
  the now-unused `import pytest`) from `test_scheduling_task_does_not_leak`
  per Step 5. Also updated `test_image_files_follows_dockerfile_copy`, whose
  final assertion (`"maf_dim.py" in names`) pinned the exact leak this task
  closes — after the fix, the real scheduling task's Dockerfile no longer
  COPYs a directory at all, so that assertion is now inverted
  (`"maf_dim.py" not in names`) and directory-expansion coverage was moved
  to a new synthetic test, `test_image_files_expands_directory_copy`, built
  from the file's own `_task_with_dockerfile` helper (same pattern used by
  every other parser-edge-case test in the file) so the audit's directory-
  expansion logic stays covered independently of what the real task
  happens to emit.
- `forge/maf/core.py` — one-line module-docstring fix (see below); not in
  the brief's file list, done as a drive-by correction since the sentence
  was now literally false and directly on-topic.
- `docs/DESIGN.md` — §5 ASCII diagram updated to show `tests/lib/` (context
  item 3).

## harbor.py docstring: before / after

Before:
```
"""Render a Dimension + instance into a runnable Harbor 0.18 task directory.

Single source of truth: the dimension's Python module is *copied* into the task
(with its one internal import rewritten), so the in-container verifier grades
with exactly the code the selfcheck battery validated.
"""
```

After:
```
"""Render a Dimension + instance into a runnable Harbor 0.18 task directory.

Single source of truth: the dimension's Python module is *copied* (with its one
internal import rewritten) into ``tests/lib/``, which Harbor uploads only at
verification time -- after the agent phase completes. The in-container
verifier therefore grades with exactly the code the selfcheck battery
validated, without ever shipping that code (``generate``/``ORACLE``/``verify``/
``CHEATERS``) to a place the agent can read it.
"""
```

The old wording ("copied into the task... so the in-container verifier
grades with exactly the code") was the invariant that caused the exploit: it
described identity-of-code as achieved by shipping the module into the task
generally, without distinguishing "the task" (which includes the agent's own
`environment/`) from "a place the agent cannot read." The new wording keeps
the true, still-needed intent (identical grading between selfcheck and the
in-container verifier) but ties it explicitly to `tests/lib/` and to Harbor's
upload timing, and spells out that this specifically excludes ever handing
`generate`/`ORACLE`/`verify`/`CHEATERS` to the agent.

Also fixed a related but out-of-brief inaccuracy in `forge/maf/core.py`'s
module docstring, which said "This module is copied verbatim into each
generated task's `environment/lib`" — now reads "into each generated task's
`tests/lib` -- which Harbor uploads only at verification time, never into
the agent's image".

## docs/DESIGN.md §5 diagram: before / after

Before (`tests/` only listed `test.sh` and `verify.py`):
```
├── tests/
│   ├── test.sh          # runs verify.py, writes reward ∈ [0,1] to /logs/verifier/reward.txt
│   └── verify.py        # pure-Python: artifact/log vs ground truth → continuous reward
```

After:
```
├── tests/
│   ├── test.sh          # runs verify.py, writes reward ∈ [0,1] to /logs/verifier/reward.txt
│   ├── verify.py        # pure-Python: artifact/log vs ground truth → continuous reward
│   └── lib/             # the dimension module (generate/ORACLE/verify/CHEATERS) --
│                        # uploaded by Harbor only at verification time, after the
│                        # agent phase; never present in environment/, never in the image
```

(Comment column re-aligned to the same offset as the surrounding tree —
verified column-by-column with a script, not eyeballed.)

The prose paragraph immediately below the diagram ("Isolation invariant...")
was already correct — Task 1 had fixed it — so it was left as-is.

## Leak audit: before / after

Ran `audit()` against a freshly generated `parallel-scheduling` task
(seed=3, `{"n": 6, "k": 2, "trap": True}`) before and after the change.

Before (12 violations — 6 from `maf_dim.py`, 6 from `maf_core.py`, both
copied into `environment/lib` and both pulled in by `COPY lib /app/lib`):
```
environment/lib/maf_dim.py: grading machinery 'def generate(' in agent image
environment/lib/maf_dim.py: grading machinery 'ORACLE' in agent image
environment/lib/maf_dim.py: grading machinery 'CHEATERS' in agent image
environment/lib/maf_dim.py: grading machinery 'def verify(' in agent image
environment/lib/maf_dim.py: grading machinery 'def ablate(' in agent image
environment/lib/maf_dim.py: grading machinery 'DIFFICULTY_PRESETS' in agent image
environment/lib/maf_core.py: grading machinery 'def generate(' in agent image
environment/lib/maf_core.py: grading machinery 'ORACLE' in agent image
environment/lib/maf_core.py: grading machinery 'CHEATERS' in agent image
environment/lib/maf_core.py: grading machinery 'def verify(' in agent image
environment/lib/maf_core.py: grading machinery 'def ablate(' in agent image
environment/lib/maf_core.py: grading machinery 'DIFFICULTY_PRESETS' in agent image
```
This confirms the brief's context note precisely: 12 violations, not 6 —
`forge/maf/core.py`'s `Dimension` protocol contains the same forbidden
markers as the dimension module itself, so it needed to leave the image too.

After: `audit() == []` (0 violations).

## End-to-end exploit check (brief Step 7)

```
$ .venv/bin/python -m forge.forge_cli gen --dim parallel-scheduling --seed 3 --difficulty medium --out /tmp/leakcheck
$ find /tmp/leakcheck -type f | sort
/tmp/leakcheck/parallel-scheduling-0003/environment/Dockerfile
/tmp/leakcheck/parallel-scheduling-0003/environment/task.json
/tmp/leakcheck/parallel-scheduling-0003/instruction.md
/tmp/leakcheck/parallel-scheduling-0003/solution/solve.sh
/tmp/leakcheck/parallel-scheduling-0003/task.toml
/tmp/leakcheck/parallel-scheduling-0003/tests/ground_truth.json
/tmp/leakcheck/parallel-scheduling-0003/tests/lib/maf_core.py
/tmp/leakcheck/parallel-scheduling-0003/tests/lib/maf_dim.py
/tmp/leakcheck/parallel-scheduling-0003/tests/test.sh
/tmp/leakcheck/parallel-scheduling-0003/tests/verify.py
/tmp/leakcheck/parallel-scheduling-0003/tests/verify_config.json
```

`environment/` contains only `Dockerfile` and `task.json` — no `lib/`. The
Dockerfile itself confirms it:
```
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends tmux git curl ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY task.json /app/task.json
```
No `COPY lib /app/lib` line. The generator/verifier/oracle are not built
into the agent's image at all, so there is nothing left in the image for a
seed brute-force to regenerate and read `_planted` from. `tests/lib/` (where
the module now lives) is only uploaded by Harbor inside `verifier.verify()`,
which the source at `harbor/verifier/verifier.py:147` confirms runs after
the agent phase — the module simply does not exist on disk while the agent
is running.

I also went one step further than the brief's Step 7 (which only checks
directory listing) and manually exercised the relocated module exactly the
way `verify_entry.py` does at grading time — `sys.path.insert(0,
".../tests/lib")`, `import maf_dim`, load `task.json` + `ground_truth.json`,
call `maf_dim.verify(...)` on the planted oracle solution from `solve.sh` —
to make sure the path change didn't silently break real grading:
```
reward 1.0 {'reward': 1.0, 'gate': 1, 'quality': 1.0,
            'subscores': {'makespan': 10, 'opt_makespan': 10}}
```
Confirms grading still works correctly through the new location.

## Test results

Baseline (before any change): `56 passed, 1 xfailed` (the xfail was
`test_scheduling_task_does_not_leak`).

Full suite after all changes: `.venv/bin/python -m pytest forge/tests/ -v`
→ **59 passed, 0 failed, 0 xfailed** (59 = 56 baseline + 2 new tests from
Step 1 + 1 new synthetic directory-expansion test in test_leak_audit.py, and
the xfail converted to a real pass).

Confirmed the un-xfailed test passes on its own merits (not just "no longer
marked xfail but silently broken"): ran
`test_scheduling_task_does_not_leak` and `test_agent_image_hides_ground_truth_and_grader`
individually and inspected `audit()`'s actual return value (`[]`), not just
the test's pass/fail status.

Interactive-dimension tests (`test_theory_of_mind.py`,
`test_failure_recovery.py`) all still pass — confirmed neither file calls
`write_task`, matching the brief's claim that they're in-process only.

## Things that surprised me / worth flagging

1. **Scope crept slightly beyond the brief's file list, but only along the
   forced path of the relocation itself.** The brief listed
   `forge/tests/test_harbor.py:23-30` as the only test-file range to touch,
   but `test_write_task_produces_valid_tree` (lines 8-20) and
   `test_copied_module_has_no_package_imports` (then lines 33-38) both
   hard-coded `environment/lib/maf_{core,dim}.py` and would have failed
   immediately after Step 3 regardless of Step 1. I fixed the path in both
   rather than leaving them red, since the alternative was shipping a task
   that fails its own pre-existing test suite. This is a path correction to
   match the new (intended) file location, not a weakening of what either
   test verifies.
2. **`test_image_files_follows_dockerfile_copy` was built to pin the leak
   itself.** Its final assertion, and its comment, explicitly said the point
   of the test was to keep directory-expansion covered "while the leak
   itself remains open." Once the leak closes, that assertion is
   necessarily false for the real task (there's no more directory COPY to
   expand), so I inverted it and moved the directory-expansion coverage to
   a synthetic Dockerfile fixture, consistent with how every other
   COPY-parsing edge case in that file is tested. I did not delete or
   weaken the coverage — I relocated it to a fixture that doesn't depend on
   a leak existing.
3. **The `_copy_runtime` signature literally matches the brief's stated
   "Produces" interface** (`_copy_runtime(dim, lib_dir: Path, include_cli:
   bool)`), which the brief says Plan 2 will call directly with a sidecar's
   lib dir — worth flagging to whoever picks up Plan 2 that this signature
   is now load-bearing for them, not just internal to `write_task`.
4. **`_write_interactive` is now guaranteed-broken for real rendering** (its
   Dockerfile's `COPY lib /app/lib` has nothing to copy from, since
   `_copy_runtime` no longer touches `environment/lib` for any dimension,
   interactive or not). I confirmed no current test exercises
   `write_task` for `theory-of-mind` or `failure-recovery`, so this doesn't
   show up as a test failure today, but it is a real, un-tested breakage
   sitting in the codebase until Task 6 quarantines/fixes interactive
   dimensions. Flagging this explicitly per the instruction to report
   rather than route around it.
5. Nothing else surprised me — the Harbor source facts in the brief
   (`verifier.py:147`, `paths.py:104`) matched what I could independently
   infer from behavior, and the fix was a clean, mechanical relocation.
