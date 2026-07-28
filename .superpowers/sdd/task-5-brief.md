### Task 5: Adversarial regression tests

The executed exploits become permanent tests. Exploits 1, 3, and 4 are structural after Task 3 — the files are gone — so they assert absence from the agent image.

**Exploit 2 is deliberately not covered here.** Forging the graded artifact is an interactive-dimension attack: it works because the verifier counts `asks` out of an agent-written transcript. `parallel-scheduling`'s submission is a schedule that `_check_schedule` (`scheduling.py:183`) independently re-executes — every dependency, skill match, and overlap re-checked, makespan recomputed — so "forging" it requires actually solving the instance. Its regression test belongs to Plan 2. Naming the gap in the module docstring is required; a test named for exploit 2 that actually checks something else would repeat the exact failure this audit found in `test_public_files_hide_ground_truth`.

**Files:**
- Create: `forge/tests/test_adversarial.py`

**Interfaces:**
- Consumes: `forge.maf.leak_audit.image_files` (Task 2), `forge.maf.harbor.write_task`.
- Produces: nothing importable.

- [ ] **Step 1: Write the tests**

Create `forge/tests/test_adversarial.py`:

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
    inst, _ = _task(tmp_path)
    partial = [{"subtask": "t0", "worker": "w0", "start": 0}]
    assert DIM.verify(inst, partial).reward == 0.0


def test_empty_submission_scores_zero(tmp_path):
    inst, _ = _task(tmp_path)
    assert DIM.verify(inst, []).reward == 0.0
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest forge/tests/test_adversarial.py -v`

Expected: PASS (5 passed). If any fails, Task 3 is incomplete — do not weaken these tests.

`test_incomplete_schedule_scores_zero` relies on `_check_schedule` (`forge/maf/dimensions/scheduling.py:198`) returning `False` when `set(seen) != set(subs)`. If it passes trivially, verify the fixture actually has more than one subtask.

- [ ] **Step 3: Commit**

```bash
git add forge/tests/test_adversarial.py
git commit -m "test: pin the four executed exploits at reward 0

Regression tests for the 2026-07-14 audit: scenario read, oracle execution,
seed brute-force, and forged submission. Each scored 1.0 before this plan."
```

---

