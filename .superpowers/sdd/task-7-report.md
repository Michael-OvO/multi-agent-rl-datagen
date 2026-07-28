# Task 7 Report — Regenerate scheduling task and verify end-to-end

Branch: `fix/isolation-and-gates`. Commit: `8f587e8` "chore(tasks): regenerate scheduling task without the leak".

## Summary

The central claim — that relocating the dimension module to `tests/lib/` still
lets in-container grading work — is **verified for real**, in Docker, via
`harbor run --agent oracle`: **reward 1.0**. The regenerated task's leak audit
went from **14 violations to 0**. All three of the brief's known loose ends
(`dryrun_local.py`, `verify_all.sh`, `RESULTS.md`) are fixed and verified.
Full unit suite: **70 passed, 2 xfailed**, no regressions from a 70/2 baseline
taken before any change.

## Step 1 — Regenerate

```
rm -rf tasks/parallel-scheduling-0003
.venv/bin/python -m forge.forge_cli gen --dim parallel-scheduling --seed 3 --difficulty medium --out tasks
```

Output:
```json
{
  "dim": "parallel-scheduling",
  "requested": 1,
  "shipped": 1,
  "rejected": [],
  "dirs": ["tasks/parallel-scheduling-0003"]
}
```

Regenerated file layout (11 files):
```
environment/Dockerfile
environment/task.json
instruction.md
solution/solve.sh
task.toml
tests/ground_truth.json
tests/lib/maf_core.py
tests/lib/maf_dim.py
tests/test.sh
tests/verify.py
tests/verify_config.json
```

Compare to the stale committed version this replaced: it had
`environment/lib/maf_core.py`, `environment/lib/maf_dim.py`, and
(untracked, gitignored, but physically present on disk before this task
started) `environment/lib/__pycache__/{maf_core,maf_dim}.cpython-313.pyc`,
plus a Dockerfile with `COPY lib /app/lib`.

## Step 2 — Audit before/after

**Before** (the stale, pre-Task-3 committed state, reconstructed exactly by
checking out HEAD and re-running `compileall` to reproduce the `.pyc` files
that were on disk when this task began — see "Note on methodology" below):

```
files in agent image: ['environment/task.json', 'environment/lib/maf_dim.py',
'environment/lib/maf_core.py', 'environment/lib/__pycache__/maf_dim.cpython-313.pyc',
'environment/lib/__pycache__/maf_core.cpython-313.pyc']
violation count: 14
 - environment/lib/maf_dim.py: grading machinery 'def generate(' in agent image
 - environment/lib/maf_dim.py: grading machinery 'ORACLE' in agent image
 - environment/lib/maf_dim.py: grading machinery 'CHEATERS' in agent image
 - environment/lib/maf_dim.py: grading machinery 'def verify(' in agent image
 - environment/lib/maf_dim.py: grading machinery 'def ablate(' in agent image
 - environment/lib/maf_dim.py: grading machinery 'DIFFICULTY_PRESETS' in agent image
 - environment/lib/maf_core.py: grading machinery 'def generate(' in agent image
 - environment/lib/maf_core.py: grading machinery 'ORACLE' in agent image
 - environment/lib/maf_core.py: grading machinery 'CHEATERS' in agent image
 - environment/lib/maf_core.py: grading machinery 'def verify(' in agent image
 - environment/lib/maf_core.py: grading machinery 'def ablate(' in agent image
 - environment/lib/maf_core.py: grading machinery 'DIFFICULTY_PRESETS' in agent image
 - environment/lib/__pycache__/maf_dim.cpython-313.pyc: compiled Python bytecode in
   agent image -- unauditable (grading markers survive compilation and a module can
   be imported from bytecode alone, with no .py source present)
 - environment/lib/__pycache__/maf_core.cpython-313.pyc: compiled Python bytecode in
   agent image -- unauditable (...)
```

This matches the brief's stated "14 violations, including the two `.pyc`
files" exactly.

**After** (regenerated task, Step 2's exact command from the brief):

```python
from pathlib import Path
from forge.maf.leak_audit import audit, image_files
d = sorted(Path('tasks').glob('parallel-scheduling-*'))[0]
print('files in agent image:', [str(p.relative_to(d)) for p in image_files(d)])
print('violations:', audit(d))
```

```
files in agent image: ['environment/task.json']
violations: []
```

**14 → 0, confirmed.**

### Note on methodology

I ran Step 1's `rm -rf` before recording the "before" state, exactly as the
brief instructs. To still get an exact, reproducible before/after diff (not
just trust the brief's stated number), I recovered the stale committed layout
with `git checkout -- tasks/parallel-scheduling-0003`, then reconstructed the
`.pyc` files with `python -m compileall` (they are untracked/gitignored, so
`git checkout` alone doesn't restore them) before running the audit. This
reproduces the exact disk state described in the brief and independently
confirms 14 violations rather than merely repeating the brief's claim.

I initially tried to do this via `git stash -u`, which went wrong: popping a
stash after an intervening `rm -rf` left the regenerated task directory
missing several files (`environment/task.json`, `instruction.md`,
`task.toml`, `solution/solve.sh`, `tests/ground_truth.json`, `tests/test.sh`,
`tests/verify_config.json` were all silently dropped by git's 3-way merge
during the pop). I caught this by re-running `find` on the task directory
before trusting the state, discarded the corrupted result with
`git checkout -- tasks/parallel-scheduling-0003 && rm -rf ...`, and simply
re-ran the generator cleanly from scratch. Final `find` confirmed all 11
expected files present before proceeding. This is called out because it's
the kind of self-inflicted state corruption that could have silently produced
a bogus "clean" audit result if I hadn't re-verified the file listing.

## Step 3 — Confirm exploit 4 is dead

```python
from pathlib import Path
d = sorted(Path('tasks').glob('parallel-scheduling-*'))[0]
assert not (d / 'environment' / 'lib').exists(), 'lib still in image'
assert (d / 'tests' / 'lib' / 'maf_dim.py').exists(), 'verifier lost its module'
print('generator absent from image; present for the verifier. Exploit 4 is dead.')
```

Output: `generator absent from image; present for the verifier. Exploit 4 is dead.`

## Step 4 — Harbor end-to-end with the oracle (the central claim)

Docker (28.4.0) and Harbor (0.18.0) are both available in this environment
and were used for real — no mocking, no skip.

Command:
```
harbor run --path tasks/parallel-scheduling-0003 --agent oracle -n 1
```

Full output (progress-spinner ANSI codes stripped; final summary reproduced
verbatim):

```
adhoc • oracle
┏━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━┓
┃ Trials ┃ Exceptions ┃  Mean ┃
┡━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━┩
│      1 │          0 │ 1.000 │
└────────┴────────────┴───────┘

┏━━━━━━━━┳━━━━━━━┓
┃ Reward ┃ Count ┃
┡━━━━━━━━╇━━━━━━━┩
│ 1.0    │     1 │
└────────┴───────┘

Job Info
Total runtime: 1m 3s
Results written to jobs/2026-07-14__22-36-47/result.json
Inspect results by running `harbor view jobs`
Share results by running `harbor upload jobs/2026-07-14__22-36-47`
```

Corroborated by `jobs/2026-07-14__22-36-47/result.json`:
```json
{
    "stats": {
        "n_completed_trials": 1,
        "n_errored_trials": 0,
        "evals": {
            "oracle__adhoc": {
                "n_trials": 1,
                "n_errors": 0,
                "metrics": [{"mean": 1.0}],
                "reward_stats": {
                    "reward": {"1.0": ["parallel-scheduling-0003__nPZKKan"]}
                },
                "exception_stats": {}
            }
        }
    }
}
```

**Reward 1.0, 0 exceptions, in real Docker.** The `sys.path.insert(0,
"/tests/lib")` in `forge/maf/runtime/verify_entry.py:34` is correct: Harbor
uploads `tests/` at verification time and the verifier finds `maf_dim.py`
there. The regenerated task's `tests/verify.py` diff against the stale
version confirms the fix that made this possible:

```diff
-    sys.path.insert(0, "/app/lib")
+    sys.path.insert(0, "/tests/lib")
```

and the Dockerfile diff confirms the module no longer ships to the agent:

```diff
 WORKDIR /app
 COPY task.json /app/task.json
-COPY lib /app/lib
```

No leftover containers from this run needed cleanup — Harbor tears its own
down after each trial. (There were pre-existing, unrelated stale containers
from an earlier session — `parallel-scheduling-0003__buxjvfd__env-*`, ~6h
old — present before this task started; left untouched as out of scope.)

## Loose end 2 — `scripts/dryrun_local.py`

Was hardcoded to `task / "environment" / "lib"`, which no longer exists after
regeneration. Fixed to `task / "tests" / "lib"` (matching `write_task`'s
actual output), and updated the docstring to match.

Ran it after the fix:
```
$ .venv/bin/python scripts/dryrun_local.py
[OK ] parallel-scheduling-0003     oracle reward = 1.0 ({'makespan': 10, 'opt_makespan': 10})

ALL PASS
```

This independently corroborates the Harbor result (same reward, computed
without Docker, importing straight from `tests/lib`).

## Loose end 3 — `scripts/verify_all.sh`

Was globbing `tasks/parallel-scheduling-* tasks/failure-recovery-*
tasks/theory-of-mind-*`. The latter two dirs were deleted by Task 6's
quarantine commit (`b568f42`) and `forge_cli` now refuses to regenerate them
(`QUARANTINED` dict), so those globs matched nothing and, under `set -euo
pipefail` with no `nullglob`, would pass the literal unexpanded glob string
to `harbor run --path`, which does not exist as a directory, and fail.

Fixed by narrowing to `tasks=(tasks/parallel-scheduling-*)`, with a comment
explaining why the other two are gone. Verified the fix with `bash -n` (syntax
check) and a dry run of the array expansion showing it resolves to the real,
existing `tasks/parallel-scheduling-0003` directory. Did not re-run the full
script's `harbor run` (already verified live via Step 4 above using the same
underlying command).

## Loose end 4 — `docs/RESULTS.md`

Added a dated (`2026-07-14`) note at the top of the file stating:
- `theory-of-mind` and `failure-recovery` are quarantined per
  `forge/forge_cli.py:QUARANTINED`, and why (ground truth reads at runtime
  inside the agent container; relocating the module can't fix that the way
  it fixed `parallel-scheduling`).
- Both constructs are separately degenerate as reward signals:
  `theory-of-mind`'s instruction states its own optimal algorithm (both
  models tested hit `asks == q_opt` on 12/12 sweep runs — this specific
  figure is sourced from `forge/tests/test_theory_of_mind.py`'s xfail
  reason and the plan doc, both already in the repo);
  `failure-recovery`'s worker roster is dispatched in pre-sorted order
  (confirmed directly in `forge/maf/dimensions/failure_recovery.py`'s
  docstring and cheater implementations, which literally say "rostered
  workers in sorted order" / `sorted(roster[t])[0]`).
- The existing rows/figures for these two dimensions are **not deleted** and
  **not claimed fabricated** — they were really measured — but are now
  explicitly flagged as not usable as capability evidence.
- Also added one sentence near the "Reproduce" line noting both
  `verify_all.sh` and `dryrun_local.py` now only exercise
  `parallel-scheduling`.

I did not invent the "pre-sorted roster" framing — I verified it against the
actual dimension source before writing the note (grep for `sort`/`roster` in
`forge/maf/dimensions/failure_recovery.py`, which shows cheaters doing
`sorted(roster[t])[0]`). I deliberately did **not** claim
`failure-recovery` "scored 1.0 for both models at every difficulty" the way
`theory-of-mind` did — RESULTS.md's own §3 table already shows
`failure-recovery` scoring 0.75 and 0.00 in two of its three recorded runs,
so that stronger claim would contradict data already in the file. The note's
wording about failure-recovery is deliberately weaker/more general
("collapses the intended skill signal") to stay accurate to what's actually
evidenced in-repo.

## Step 5 — Full test suite

Baseline (before any change in this task): `70 passed, 2 xfailed`.
Final (after regeneration + all fixes): `70 passed, 2 xfailed`. Identical —
no regressions.

```
.venv/bin/python -m pytest forge/tests/ -v
...
======================== 70 passed, 2 xfailed in 0.19s =========================
```

The 2 xfailed are the pre-existing, intentional `strict=True` xfails in
`test_failure_recovery.py::test_selfcheck_passes` and
`test_theory_of_mind.py::test_selfcheck_passes`, documenting exactly the
quarantine reasons above — unrelated to this task's changes.

## Step 6 — Commit

```
git add tasks/ scripts/dryrun_local.py scripts/verify_all.sh docs/RESULTS.md
git commit -m "chore(tasks): regenerate scheduling task without the leak ..."
```

Commit: `8f587e8`.

```
 docs/RESULTS.md                                    | 28 +++++++++++++++++++++-
 scripts/dryrun_local.py                            |  9 +++++--
 scripts/verify_all.sh                              |  7 +++++-
 tasks/parallel-scheduling-0003/environment/Dockerfile |  1 -
 tasks/parallel-scheduling-0003/{environment => tests}/lib/maf_core.py | 3 ++-
 tasks/parallel-scheduling-0003/{environment => tests}/lib/maf_dim.py  | 6 +++++
 tasks/parallel-scheduling-0003/tests/verify.py     |  2 +-
 7 files changed, 49 insertions(+), 7 deletions(-)
```

`git status` after commit shows only the pre-existing, unrelated untracked
`sources/` directory (a stray empty-file scratch dir unrelated to this task,
present since before this session started) — left untouched, not added.

## Things that surprised me

1. **The `git stash -u` / `rm -rf` / `git stash pop` sequence silently
   corrupted the regenerated task directory** (dropped 7 of 11 files without
   any error or warning from git). This was purely my own tooling mistake
   while trying to preserve the "before" state for comparison, not a defect
   in any of the plan's code — but it's a good illustration of why
   `image_files()`/`audit()` re-verifying from scratch, rather than trusting
   intermediate state, matters. I caught it by re-listing files rather than
   trusting the stash pop's reported success, discarded the bad state, and
   regenerated cleanly.
2. Everything else was unsurprising in the good way: the audit's before/after
   counts matched the brief's stated numbers exactly (14 → 0), `harbor run`
   worked on the first real attempt with no image-build or network issues,
   and `dryrun_local.py` (no Docker) and `harbor run` (real Docker) agreed on
   reward 1.0 by two independent code paths.
3. Pre-existing, unrelated leftover Docker containers
   (`parallel-scheduling-0003__buxjvfd__env-*`, from a prior session, ~6h old)
   were present in `docker ps` both before and after this task's `harbor run`
   — confirmed they're untouched/irrelevant to this task's own trial
   (`...__nPZKKan__...`), which Harbor cleaned up itself.
