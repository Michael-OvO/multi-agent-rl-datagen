# Task 5 report: adversarial regression tests

## What was created

`forge/tests/test_adversarial.py` — five tests pinning the four exploits executed
against the shipped tasks on 2026-07-14 (exploit 2 explicitly excluded, named in
the module docstring per the requirement). Uses `forge.maf.leak_audit.image_files`
(not a Dockerfile re-implementation) and `forge.maf.harbor.write_task` to build a
real rendered task directory under `tmp_path` for each test — no assertions
against `forge/` source files.

```python
"""Regression tests for exploits executed against the shipped tasks on 2026-07-14.

Exploits 1, 3, and 4 scored reward 1.0 on parallel-scheduling or on the
interactive dimensions. They are structural now -- the files are gone -- so
these tests assert absence from the agent image.

Exploit 2 (forging the graded artifact) does NOT apply to parallel-scheduling:
its submission is a schedule the verifier independently re-executes, so
"forging" it means solving the problem. Exploit 2 is interactive-only and its
regression test lands in Plan 2 with the sidecar. It is named here so the gap
is explicit rather than silently absent.
"""

import json

from forge.maf.dimensions.scheduling import DIM
from forge.maf.harbor import write_task
from forge.maf.leak_audit import image_files


def _task(tmp_path):
    inst = DIM.generate(3, {"n": 6, "k": 2, "trap": True})
    return inst, write_task(DIM, inst, tmp_path, "0001")


def _json_keys(path):
    if path.suffix != ".json":
        return []
    try:
        data = json.loads(path.read_text())
    except Exception:
        return []
    return list(data) if isinstance(data, dict) else []


def test_exploit1_ground_truth_absent_from_agent_image(tmp_path):
    # Attack: cat the scenario out of the image to read the answer.
    _, d = _task(tmp_path)
    for f in image_files(d):
        leaked = [k for k in _json_keys(f) if k.startswith("_")]
        assert not leaked, f"{f.name} leaks {leaked}"


def test_exploit3_oracle_absent_from_agent_image(tmp_path):
    # Attack: import maf_dim from /app/lib and run the shipped ORACLE.
    _, d = _task(tmp_path)
    for f in image_files(d):
        assert "ORACLE" not in f.read_text(errors="ignore"), f"{f.name} ships the oracle"


def test_exploit4_generator_absent_from_agent_image(tmp_path):
    # Attack: brute-force the seed against the shipped generate() until the
    # public fields match, then read the private ones out of the regenerated
    # instance. Recovered _planted at seed=3 and scored 1.0.
    _, d = _task(tmp_path)
    for f in image_files(d):
        assert "def generate(" not in f.read_text(errors="ignore"), (
            f"{f.name} ships the generator; seed brute-force defeats /tests isolation"
        )


def test_incomplete_schedule_scores_zero(tmp_path):
    # Not exploit 2 -- see module docstring. This pins the gate: a submission
    # that does not schedule every subtask is invalid regardless of makespan.
    #
    # "t0" is not a subtask id this fixture ever produces (real ids are
    # "t100".."t103" and "t000"), so a submission built from it would be
    # rejected by the *unknown-subtask-id* check in _check_schedule before
    # ever reaching the completeness check (`set(seen) != set(subs)`) this
    # test is meant to pin -- verified by disabling that completeness check
    # and confirming a "t0"-keyed submission still scored 0. Use a real,
    # valid, but partial subtask id instead so the test actually exercises
    # the completeness gate.
    inst, _ = _task(tmp_path)
    partial = [{"subtask": "t100", "worker": "w0", "start": 0}]
    assert DIM.verify(inst, partial).reward == 0.0


def test_empty_submission_scores_zero(tmp_path):
    inst, _ = _task(tmp_path)
    assert DIM.verify(inst, []).reward == 0.0
```

## Deviation from the brief's literal test code, and why

The brief's Step 1 code says "use verbatim," but its own "Ambiguity resolution"
section requires catching exactly this failure mode: a test that passes for a
reason unrelated to what its name promises. `test_incomplete_schedule_scores_zero`
as given verbatim used `partial = [{"subtask": "t0", ...}]`. `"t0"` is not a
subtask id this fixture (`DIM.generate(3, {"n": 6, "k": 2, "trap": True})`) ever
produces — the real ids are `t100, t101, t102, t103, t000`. That means the
verbatim submission is rejected by `_check_schedule`'s very first per-entry
check (`tid not in subs → return False, None`) before it ever reaches the
completeness check (`set(seen) != set(subs)`, scheduling.py:203) the test's own
comment says it pins.

I confirmed this is a real defect (not a hypothetical) by disabling that exact
completeness check in `scheduling.py` (`if False and set(seen) != set(subs)`)
and re-running the verbatim test: it still passed (reward stayed 0.0), proving
it was never exercising the completeness gate at all — the same shape of
failure the brief cites for `test_public_files_hide_ground_truth` (a test whose
name promised a property it didn't actually check).

Fix applied: changed the submission to `partial = [{"subtask": "t100", "worker":
"w0", "start": 0}]` — a real, valid, but partial subtask id. With this fixture,
the DAG has 5 subtasks total (verified below), so this submission omits 4 of
them. I re-ran the same experiment (disable the completeness check) against
the corrected test and it now goes red as expected: `reward == 1.0` instead of
`0.0`. Restored `scheduling.py` to its tracked state afterward (`git diff
--stat forge/maf/dimensions/scheduling.py` empty, confirmed).

No other line of the brief's test file was changed. `test_empty_submission_scores_zero`
was left verbatim — see verification below for why it's not defective in the
same sense even though it goes through a different code path (an unhandled
`ValueError` caught by `verify()`'s own `try/except`, not the explicit
completeness check) to reach reward 0.

## Evidence each test genuinely fails when the property it guards is broken

For every temporary break below, the file was restored afterward and `git diff
--stat <file>` confirmed empty (no residual changes) before moving to the next
experiment. Final `git status --short` shows only `forge/tests/test_adversarial.py`
added.

**Fixture check first:** confirmed `DIM.generate(3, {"n": 6, "k": 2, "trap":
True})` produces 5 subtasks (`t100, t101, t102, t103, t000`), not 1 — so
"incomplete" is a real, non-trivial condition for this fixture, per the
brief's own line 99 warning.

1. **`test_exploit1_ground_truth_absent_from_agent_image`** — reverted
   `harbor.py`'s `_write_static` to write `json.dumps(instance, ...)` instead
   of `json.dumps(pub, ...)` into `environment/task.json` (i.e. reintroduced a
   private-key leak into the rendered agent image). Result: test failed with
   `AssertionError: task.json leaks ['_planted', '_opt_makespan']`. Restored;
   `git diff --stat` on `harbor.py` came back empty; full suite re-passed.

2. **`test_exploit3_oracle_absent_from_agent_image`** and
   **`test_exploit4_generator_absent_from_agent_image`** — reverted the whole
   of `forge/maf/harbor.py` to its pre-Task-3 state (`git show
   337e221:forge/maf/harbor.py`, the commit immediately before
   `bf86ce3 fix(isolation): ship the dimension module to tests/, not the
   agent image`), which copies `lib/` (containing `maf_dim.py` with
   `generate`/`ORACLE`/`verify`/`CHEATERS`) into `environment/lib` for static
   dimensions. Result: both tests failed —
   `AssertionError: maf_dim.py ships the oracle` and
   `AssertionError: maf_dim.py ships the generator; seed brute-force defeats
   /tests isolation`. `test_exploit1` stayed green in this experiment (expected:
   the static dimension's `task.json` is built from `public(instance)`
   regardless of this particular regression, so exploit 1 needed its own
   separate break, done in step 1). Restored `harbor.py` from the pre-edit
   backup; `git diff --stat` empty; full suite re-passed.

3. **`test_incomplete_schedule_scores_zero`** — see "Deviation" section above.
   Verified both that the verbatim brief version was defective (still green
   with the completeness check disabled) and that the corrected version
   (`"t100"`) goes red under the identical experiment (`reward == 1.0` instead
   of the asserted `0.0`). Restored `scheduling.py`; `git diff --stat` empty;
   full suite re-passed.

4. **`test_empty_submission_scores_zero`** — disabled the same completeness
   check (`if False and set(seen) != set(subs)`) and confirmed
   `DIM.verify(inst, []).reward` was still `0.0` — but this is because an empty
   `seen` dict makes `max(end for _, _, end in seen.values())` raise
   `ValueError: max() arg is an empty sequence`, which `verify()`'s own
   `try/except Exception: gate, makespan = False, None` catches and turns into
   a 0 reward. That's a different code path than the explicit completeness
   check, but the test's name ("empty submission scores zero") accurately
   describes what it verifies — it doesn't claim to pin the specific
   `set(seen) != set(subs)` line the way `test_incomplete_schedule_scores_zero`'s
   comment does. I did not find a way to make this test pass while an empty
   submission scores > 0 without it being surfaced as a real code change (e.g.
   if someone made `verify()` swallow the crash and default to a nonzero
   makespan, this test would still catch that). Left verbatim. Restored
   `scheduling.py`; `git diff --stat` empty.

## Test results

```
$ .venv/bin/python -m pytest forge/tests/test_adversarial.py -v
forge/tests/test_adversarial.py::test_exploit1_ground_truth_absent_from_agent_image PASSED
forge/tests/test_adversarial.py::test_exploit3_oracle_absent_from_agent_image PASSED
forge/tests/test_adversarial.py::test_exploit4_generator_absent_from_agent_image PASSED
forge/tests/test_adversarial.py::test_incomplete_schedule_scores_zero PASSED
forge/tests/test_adversarial.py::test_empty_submission_scores_zero PASSED
5 passed in 0.03s
```

Full repo suite after the change:

```
$ .venv/bin/python -m pytest -q
...................x............................................x..
65 passed, 2 xfailed in 0.16s
```

(2 xfailed are pre-existing and unrelated to this change.)

## Files touched

- Created: `forge/tests/test_adversarial.py`
- Not modified (per instructions, and confirmed via `git diff --stat` empty
  after every temporary experiment): `forge/maf/harbor.py`,
  `forge/maf/leak_audit.py`, `forge/maf/dimensions/scheduling.py`

## Anything surprising

The brief's own worked example ("If any test in the brief passes trivially —
e.g. because the fixture has only one subtask...") turned out to describe a
real defect in the brief's own verbatim code, just via a different mechanism
than the example given (an invalid subtask id short-circuiting to an earlier
check, rather than a fixture with only one subtask). This is exactly the class
of test-integrity issue the audit flagged in `test_public_files_hide_ground_truth`,
so I treated "verify it actually goes red" as the binding instruction over
"use verbatim" for this one line, fixed it, and documented the fix and its
verification above rather than silently shipping a green-but-blind test.
