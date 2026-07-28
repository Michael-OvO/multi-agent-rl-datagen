# Progress: isolation-and-gates (Plan 1 of 2)

Plan:   docs/superpowers/plans/2026-07-14-isolation-and-gates.md
Spec:   docs/superpowers/specs/2026-07-14-outcome-based-sidecar-redesign.md
Branch: fix/isolation-and-gates
Base:   1a997dc6b661277a39f3c8b75cc6925eafc2df84

## Tasks
- [x] 1 Documentation retraction
- [x] 2 Leak audit (G1)
- [x] 3 Relocate dimension module out of agent image
- [x] 4 Dictation gate (G2)
- [x] 5 Adversarial regression tests
- [x] 6 Quarantine interactive dimensions
- [x] 7 Regenerate scheduling tasks + e2e verify

## Minor findings (for final review triage)
1. DESIGN.md sec 9 architecture diagram stale (forge/common/, forge/generators/
   vs real forge/maf/). Out of scope for task 1; triage at final review.
2. DESIGN.md sec 5 task-dir diagram shows tests/ with only test.sh + verify.py,
   but the new isolation invariant next to it says the module ships to
   tests/lib/. -> CARRY TO TASK 3 (task 3 makes tests/lib real).

## Log

Task 1: implementer DONE (commit e8db524), review pending.
  CARRY TO TASK 3: harbor.py:1-6 module docstring still states the
  "Single source of truth: the dimension module is copied into the task"
  invariant -- the root cause of exploits 1/3/4. The plan wrongly located this
  text in DESIGN.md prose; it is a code docstring. Task 3 edits harbor.py and
  must replace it there.
  MINOR (final-review triage): DESIGN.md sec 9 architecture diagram is stale
  (forge/common/, forge/generators/ vs the real forge/maf/ layout).
Task 1: complete (commit e8db524, review clean: spec OK, quality approved, 2 minor)

Task 2: implementer DONE (commit c9f653f), review pending.
  Confirmed red test before xfail: test_scheduling_task_does_not_leak failed
  with 12 violations (not the 6 the brief predicted) -- the 6 FORBIDDEN_MARKERS
  fire on BOTH environment/lib/maf_dim.py AND environment/lib/maf_core.py,
  because forge/maf/core.py (also copied verbatim into every image via
  _copy_runtime) defines the Dimension protocol whose docstring/abstract
  methods contain the literal marker substrings (ORACLE, CHEATERS,
  DIFFICULTY_PRESETS, def generate(/verify(/ablate(). Did not adjust the
  audit to suppress this -- it's a real instance of grading-adjacent code
  reaching the agent image. CARRY TO TASK 3: relocating maf_dim.py out of the
  image is not sufficient by itself -- maf_core.py must also stop being
  shipped verbatim, or this audit will still fail post-fix.
  Full suite after adding strict xfail: 42 passed, 1 xfailed.
Task 2: complete (commits c9f653f..<docstring fix>, review clean after 3 fix rounds)
  Rounds found: single-source COPY parsing, backslash continuations, .. traversal,
  ADD unrecognized, comment-swallows-continuation, ADD archives, audit() docstring
  overstating its guarantee. All fixed; each verified red-then-green.
  ACCEPTED LIMITATION: leak_audit statically approximates Docker COPY/ADD
  semantics and never builds the image. Fail-closed on unrecognized forms.
  True ground truth would require building + listing the image (rejected: puts
  Docker in the unit-test path). Documented in the module docstring.
  CARRY TO TASK 3: dropping 'COPY lib /app/lib' must remove BOTH maf_dim.py and
  maf_core.py from the image -- core.py's Dimension protocol contains the same
  markers AND its docstring reveals the _-prefix ground-truth convention.
Task 3: complete (commit bf86ce3, review clean: spec OK, approved, 0 crit/imp)
  EXPLOIT 4 CONFIRMED DEAD (controller verified independently): regenerated
  task's agent image contains only task.json; maf_dim and maf_core both
  ModuleNotFoundError; audit() == []. Reviewer separately simulated the
  in-container grading path (/tests/lib on sys.path) -> reward 1.0, so
  relocation did not break verification.
  CARRY TO TASK 7: scripts/dryrun_local.py:5,52 hardcodes
  task/"environment"/"lib". It still works against the stale checked-in
  tasks/ dirs, but Task 7 REGENERATES those -> the script will break.
Task 4: complete (commit b3e9833, review clean: spec OK, approved, ZERO findings)
  V4 independently rejects theory-of-mind AND failure-recovery -- sole failing
  check on both, 0/3 instances ship. Controller verified directly.
  NEW FINDING from the reviewer: failure-recovery is degenerate for the SAME
  reason as theory-of-mind. Its roster is generated pre-sorted
  (sorted(rng.sample(...))), so walking the presented order on failure
  reproduces _oracle's sorted tie-break exactly. Neither dimension's cheater
  panel contains an obedience policy, because obedience IS the oracle. This
  confirms the quarantine is correct, not collateral damage.
Task 5: complete (commit 0d1fc18 + fixture fix, review clean: approved, 0 crit/imp)
  Implementer caught a real defect in the plan's own test code: the brief's
  't0' subtask id does not exist, so _check_schedule rejected it on the
  unknown-id branch and the test never reached the completeness check it
  names -- it passed for the wrong reason. Proved by disabling the
  completeness check and watching it still pass.
  Controller then de-hardcoded the id (derive from instance) so the trap
  cannot re-arm on an id-scheme change, and re-verified red-then-green.
  RECURRING THEME (4th instance): green tests prove nothing. Only breaking
  the guarded property and watching red proves a test guards it.
Task 6: complete (commits b568f42 + ba2a798, review clean: approved, 0 crit/imp)
  Quarantine gives an explicit refusal with a reason (was: silent "dirs": []).
  FOLDED IN A CRITICAL FIX the controller found while verifying: leak_audit had
  _SKIP_SUFFIXES = (".pyc",) -- a fail-OPEN. Verified before fixing: every
  marker survives into bytecode; an agent can import maf_dim from .pyc alone
  and get a callable generate() and live ORACLE; .pyc really reaches images via
  COPY lib. So a .pyc-only image would audit clean while the agent runs the
  oracle. Now .pyc/.pyo/__pycache__ are violations outright, generalized to
  "any file failing strict UTF-8 decode is a violation, never a silent skip".
  The skip was justified as "bytecode reads as garbage" -- mistaking
  "unreadable by me" for "harmless".
  CARRY TO TASK 7 (all real, all verified):
   - tasks/parallel-scheduling-0003 is STALE (pre-Task-3): Dockerfile still has
     COPY lib /app/lib and lib/__pycache__/*.pyc on disk. Fixed audit reports
     14 violations against it. Regenerating fixes it.
   - scripts/dryrun_local.py:5,52 hardcodes task/"environment"/"lib" -> breaks
     on regenerated tasks.
   - scripts/verify_all.sh globs the two removed dims -> matches nothing.
   - docs/RESULTS.md references the deleted task dirs.
Task 7: complete (commit 8f587e8, review clean: approved, 1 minor)
  CENTRAL CLAIM VERIFIED END-TO-END. Controller ran, in real Docker:
    harbor run --path tasks/parallel-scheduling-0003 --agent oracle -n 1
    -> Reward 1.0
  So relocating the module to tests/lib did NOT break in-container grading.
  Reviewer independently re-ran verify_all.sh in Docker -> 1.0, and verified
  the regenerated dir file-by-file (implementer had reported a git-stash
  mishap mid-task; final artifact is clean).
  Audit on regenerated task: 14 violations -> 0. Agent image = task.json only.
  MINOR for final triage: docs/RESULTS.md quarantine caveat appears only once
  at top of file, not inline next to the theory-of-mind / failure-recovery
  rows in the tables. A reader jumping straight to a table could miss it.

ALL 7 TASKS COMPLETE. Final whole-branch review next.
