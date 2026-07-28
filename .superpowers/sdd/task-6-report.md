# Task 6 Report: Quarantine the interactive dimensions

Branch: `fix/isolation-and-gates`
Commit: `b568f42b551d40548ecf87ad8651ff7395371310`

## What this task is for (context, not redundant with Gate V4)

Gate V4 (Task 4) already blocks `theory-of-mind` and `failure-recovery` from
shipping instances: `selfcheck` requires every dimension to declare
`DICTATION_CHEATER`, neither dimension has one, so both fail V4 and ship
`"shipped": 0` today. That was already true before this task.

What was still missing: the refusal was silent and unexplained. Running
`forge gen --dim theory-of-mind` produced a clean-looking JSON summary with
`"dirs": []` and no indication *why* nothing shipped — a user could easily
read that as "ran fine, just an unlucky seed" and retry with more seeds or a
different difficulty forever. This task makes the refusal happen at the CLI
entrypoint, before any generation/selfcheck work runs, with a stated reason
naming the actual cause (ground truth leaks into the agent image; needs the
Plan 2 sidecar), so the failure is explicit, immediate, and explained.

## Changes

### `forge/forge_cli.py`

Added a module-level `QUARANTINED: dict[str, str]` mapping dimension name to
reason, placed right after the imports:

```python
QUARANTINED = {
    "theory-of-mind": (
        "ground truth ships in the agent image; needs the Plan 2 sidecar. "
        "The construct is also degenerate: the instruction states the optimal "
        "algorithm (asks == q_opt on 12/12 sweep runs)."
    ),
    "failure-recovery": (
        "ground truth ships in the agent image; needs the Plan 2 sidecar."
    ),
}
```

In `gen(args)`, immediately after `reg = registry()` and before the
"unknown dimension" check:

```python
    if args.dim in QUARANTINED:
        raise SystemExit(
            f"refusing to render quarantined dimension {args.dim!r}: "
            f"{QUARANTINED[args.dim]}"
        )
```

This runs before `out.mkdir(...)`, so no output directory is created (or
populated, if it already existed) when a quarantined dimension is requested.

`registry()` itself was left unchanged — quarantined dimensions still register
normally (so `Dimension` objects remain importable/inspectable, e.g. for their
unit tests), the refusal happens only at the `gen` entrypoint.

### `forge/tests/test_forge_cli.py`

Added the two tests specified in the brief verbatim:
- `test_quarantined_dimension_cannot_be_rendered` — calls `main(["gen",
  "--dim", "theory-of-mind", "--out", str(tmp_path)])` inside
  `pytest.raises(SystemExit)`, asserts a non-zero exit code and that
  `tmp_path` stays empty.
- `test_quarantine_names_the_reason` — asserts both dimension names are keys
  in `QUARANTINED` and every reason string mentions "sidecar" (case
  insensitive).

### `tasks/theory-of-mind-0002/` and `tasks/failure-recovery-0001/` removed

`git rm -r` on both directories (24 files, all tracked). These were rendered
before Task 3's isolation fix and still carry the old `environment/lib/`
layout with the full instance embedded in `environment/scenario.json`
(verified before deletion: `_culprit`, `_q_opt`, `_chains`, `_elim` were all
present in `theory-of-mind-0002/environment/scenario.json` and
`failure-recovery-0001/environment/scenario.json` — full ground truth
readable by the agent). These were exactly the poisoned artifacts this plan
exists to stop shipping.

Only `tasks/parallel-scheduling-0003/` remains under `tasks/`.

## What a user now sees

```
$ python -m forge.forge_cli gen --dim theory-of-mind --out tasks/
refusing to render quarantined dimension 'theory-of-mind': ground truth ships
in the agent image; needs the Plan 2 sidecar. The construct is also
degenerate: the instruction states the optimal algorithm (asks == q_opt on
12/12 sweep runs).
$ echo $?
1
```

```
$ python -m forge.forge_cli gen --dim failure-recovery --out tasks/
refusing to render quarantined dimension 'failure-recovery': ground truth
ships in the agent image; needs the Plan 2 sidecar.
$ echo $?
1
```

No directory is created under `--out` in either case (verified manually
against a fresh, nonexistent output path — `ls` on it afterward reports "No
such file or directory"). Previously the same commands would print a JSON
summary with `"shipped": 0` and `"dirs": []` and exit 0, with the real cause
(missing `DICTATION_CHEATER`, degenerate construct, ground-truth leak)
invisible to the caller.

`parallel-scheduling` (and any future non-quarantined dimension) is
unaffected — `registry()` and the rest of `gen` are unchanged for it.

## Test results

- `forge/tests/test_forge_cli.py -v`: 4 passed (2 pre-existing + 2 new).
  - Before the `QUARANTINED` implementation: collection error,
    `ImportError: cannot import name 'QUARANTINED' from 'forge.forge_cli'`
    (confirmed the test fails first, per TDD step 2 of the brief).
  - After: all 4 pass.
- Full suite (`.venv/bin/python -m pytest -q` from repo root, both before and
  after the `tasks/` deletion): **67 passed, 2 xfailed**. (Baseline before
  this task's changes was 65 passed, 2 xfailed; the 2 new tests account for
  the difference. No regressions, no new xfails/xpasses.)

## What broke (reported per the brief's instruction, not worked around)

`scripts/dryrun_local.py` iterates every directory under `tasks/` and expects
each to have `tests/verify_config.json`, `environment/scenario.json` (or
`environment/task.json` + `tests/ground_truth.json`), and `environment/lib/`.
It is not part of the pytest suite and is not invoked by any test or CI (no
`.github/workflows` exist in this repo) — it's a manual verification script
documented in `README.md` and `docs/RESULTS.md`. After removing the two
quarantined task directories, running it now fails immediately:

```
$ .venv/bin/python scripts/dryrun_local.py
Traceback (most recent call last):
  ...
  File "scripts/dryrun_local.py", line 51, in main
    cfg = json.load(open(task / "tests" / "verify_config.json"))
FileNotFoundError: [Errno 2] No such file or directory: 'tasks/failure-recovery-0001/tests/verify_config.json'
```

This is expected and was flagged in advance by the brief ("If removing them
breaks other tests or scripts, report it rather than working around it. In
particular `scripts/dryrun_local.py` is known to reference the `tasks/`
example dirs."). Per instructions I did not modify `dryrun_local.py`; a
future task (presumably part of the sidecar plan, once new renderable sample
tasks exist, or a cleanup pass over docs/scripts) should either make the
script skip empty/missing dirs gracefully or update it once new sample tasks
are available.

Also noted, not fixed (same category, not explicitly named in the brief but
same root cause):

- `scripts/verify_all.sh` glob-expands `tasks/failure-recovery-*` and
  `tasks/theory-of-mind-*`; with no matches and `nullglob` unset, those
  patterns pass through as literal (nonexistent) paths to
  `harbor run --path ...`, which will fail. Also a manual-only script (needs
  Docker + Harbor), not invoked by pytest or CI.
- `docs/RESULTS.md` documents historical oracle-verification results for
  `failure-recovery-0001` and `theory-of-mind-0002` (Docker run timings,
  reward-spread tables) — this is now a stale historical record referencing
  deleted directories. Not a test/script, out of scope per the brief (which
  only asked to modify `forge/forge_cli.py`, its test file, and remove the
  two `tasks/` dirs); left untouched.
- `README.md` already only references `tasks/parallel-scheduling-0003` in its
  `harbor run` examples (that substitution was made in an earlier commit,
  `e8db524`), so no README changes were needed for this task.

## Files touched

- `/Users/michael/Documents/Kimi-RL-DataGen/forge/forge_cli.py`
- `/Users/michael/Documents/Kimi-RL-DataGen/forge/tests/test_forge_cli.py`
- Deleted: `/Users/michael/Documents/Kimi-RL-DataGen/tasks/theory-of-mind-0002/` (12 files)
- Deleted: `/Users/michael/Documents/Kimi-RL-DataGen/tasks/failure-recovery-0001/` (12 files)

Not touched (per explicit instruction): `forge/maf/dimensions/theory_of_mind.py`,
`forge/maf/dimensions/failure_recovery.py`, and their unit tests remain in
place for the later sidecar plan to build on.

---

# Addendum: G1 leak_audit.py fail-open `.pyc` fix (separate task, same label)

**Note on filename collision:** this task ("fix a CRITICAL fail-open defect in
`forge/maf/leak_audit.py` — the `.pyc` skip") was assigned to be reported at
this same path (`task-6-report.md`), but that filename was already used above
for an unrelated, previously-completed task ("Quarantine the interactive
dimensions"). Nothing above this line was touched or re-verified as part of
this addendum; it is appended, not replaced, so the prior report stays intact.
Flagging in case the numbering was meant to point elsewhere.

Branch: `fix/isolation-and-gates` (already checked out at start of this task)
Commit: `ba2a798` — `fix(maf): G1 leak_audit fails closed on compiled bytecode instead of skipping it`

## The defect

`forge/maf/leak_audit.py` had `_SKIP_SUFFIXES = (".pyc",)`, filtered out at
the top of `image_files()`. Any `.pyc` reaching the agent image (e.g. via a
`COPY lib /app/lib` directive whose `lib/` contains a `__pycache__`) was
therefore invisible to `audit()` — it never reached the ground-truth-key scan
or the `FORBIDDEN_MARKERS` substring scan, so `audit()` could return `[]` on
an image an agent could import the oracle from. Verified before touching
anything: `ORACLE`, `CHEATERS`, `generate`, `verify`, `_culprit` all survive
into `maf_dim.cpython-313.pyc`'s compiled bytes, a module imports and runs
from `.pyc` alone with no `.py` present, and the checked-in
`tasks/parallel-scheduling-0003/environment/lib/__pycache__/*.pyc` shows this
exact directory-copy path is real (that `__pycache__` is git-ignored/untracked,
not committed, but would be swept in by a real `docker build` against that
directory as it sits on disk today).

## Fix

- Removed `_SKIP_SUFFIXES` entirely. `image_files()` no longer filters
  anything by suffix — it returns every file a resolved COPY/ADD directive
  puts in the image, `.pyc` included, since downstream consumers (Tasks 3, 5,
  7) rely on this list to see everything that actually lands there.
- `audit()` now treats any file whose suffix is `.pyc`/`.pyo`, or that sits
  under a `__pycache__` directory, as a **flat violation** (new
  `_is_compiled_python()` helper) — it does not substring-scan the bytecode
  and call that coverage, per the guidance that a scan which happens to miss
  is indistinguishable from a clean result.
- Generalized beyond that: any other file that fails to decode as UTF-8 text
  (new `_decode_text()` helper, strict decode, `None` on
  `UnicodeDecodeError`/`OSError`) is also surfaced as a violation rather than
  silently skipped, closing the same class of bug for any future binary
  content, not just `.pyc`.
- Updated the module docstring with a new paragraph stating this rule
  explicitly (compiled bytecode / undecodable content is never legitimate in
  an agent image here, and fails closed).
- Did not touch `forge/maf/harbor.py` or `forge/maf/dimensions/` (per
  instruction). Kept `image_files() -> list[Path]`, `audit() -> list[str]`,
  `unparsed_copies() -> list[str]` signatures unchanged.

## Tests (written first, verified red, then green)

Added to `forge/tests/test_leak_audit.py`:
- `test_pyc_only_lib_dir_is_a_violation` — a `COPY lib /app/lib` directory
  whose only content is a real compiled `.pyc` (via `py_compile.compile`,
  stdlib) containing the `ORACLE`/`def verify(` markers, with **no** `.py`
  anywhere under `lib/`. Asserts `audit(d) != []`.
- `test_pyc_alongside_py_violation_names_pyc_not_only_py` — same `lib/` dir,
  but with `maf_dim.py` present *and* its compiled `.pyc` in
  `lib/__pycache__/`. Asserts a violation exists whose text names
  `maf_dim.cpython-313.pyc` specifically, not only `maf_dim.py`.
- `test_image_files_includes_compiled_bytecode` — a raw (non-decodable)
  `.pyc`-suffixed file under a COPYed dir; asserts it now appears in
  `image_files()`'s returned paths.

Confirmed red first: ran
`.venv/bin/python -m pytest forge/tests/test_leak_audit.py -v -k pyc` against
the unmodified module — all three failed (`assert [] != []`, the violation
list only named `maf_dim.py`, and `'module.pyc' in set()` was false),
confirming the defect and that the tests actually exercise it.

## Test results (after the fix)

Command run: `.venv/bin/python -m pytest forge/tests/test_leak_audit.py forge/tests/test_adversarial.py forge/tests/test_harbor.py -v`

Result line: `30 passed in 0.05s`

Full-suite command run: `.venv/bin/python -m pytest`
Result line: `70 passed, 2 xfailed in 0.16s` (the 2 xfailed are pre-existing,
unrelated to this change — same count as before this task's changes).

`test_scheduling_task_does_not_leak`, `test_agent_image_hides_ground_truth_and_grader`,
and the three `test_exploit*` tests in `test_adversarial.py` all stayed green
against a freshly-rendered `parallel-scheduling` task — confirming that
task's `environment/` (rendered via `write_task`, non-interactive dimension)
still carries no `lib/` directory and hence no bytecode, so nothing there was
weakened to make the suite pass.

## Concern to flag

The checked-in `tasks/parallel-scheduling-0003/environment/lib/__pycache__/`
directory (containing real `.pyc` files) is **not tracked by git**
(`.gitignore` excludes `__pycache__/`, confirmed via `git ls-files` returning
nothing for that path) — so it is not part of the committed repo. But it does
sit on disk in this checked-out working tree, next to a Dockerfile that still
reads `COPY lib /app/lib`, and that `tasks/parallel-scheduling-0003/`
directory itself predates Task 3's harbor.py refactor (which moved the
dimension module to `tests/lib/` for freshly-rendered tasks). If anyone ran
`docker build` against that specific checked-out directory as it stands
today, the `.pyc` files actually would be swept into the image — this isn't
a synthetic scenario, it's the live state of a real task directory in this
repo. Fixing that is out of scope here (not asked for, and would mean
touching `harbor.py`/regenerating tasks), but it's worth a follow-up: either
regenerate `tasks/parallel-scheduling-0003` against the current `write_task`,
or delete the stale `lib/__pycache__` bytecode from disk.
