### Task 2: Leak audit (G1)

An automated audit that fails when the agent's image contains anything that derives ground truth. Written now, against the current broken tasks, so it reproduces exploits 1/3/4 as red tests. Everything after this task is protected by it.

The audit reads the agent service's Dockerfile to determine which files actually enter the image, rather than scanning the whole rendered directory. This matters: Plan 2 puts a `docker-compose.yaml` (holding the verifier token) in `environment/`, and that file is build context, not image content.

**Files:**
- Create: `forge/maf/leak_audit.py`
- Test: `forge/tests/test_leak_audit.py`

**Interfaces:**
- Consumes: `forge.maf.harbor.write_task(dim, instance, out_dir, task_id) -> Path` (existing).
- Produces:
  - `forge.maf.leak_audit.image_files(task_dir: Path) -> list[Path]` — host paths of files the agent's Dockerfile copies into the image.
  - `forge.maf.leak_audit.audit(task_dir: Path) -> list[str]` — human-readable violations; empty list means clean. Task 3 and Task 6 both call `audit`.

- [ ] **Step 1: Write the failing test**

Create `forge/tests/test_leak_audit.py`:

```python
from forge.maf.dimensions.scheduling import DIM as SCHED
from forge.maf.harbor import write_task
from forge.maf.leak_audit import audit, image_files


def test_image_files_follows_dockerfile_copy(tmp_path):
    inst = SCHED.generate(3, {"n": 6, "k": 2, "trap": True})
    d = write_task(SCHED, inst, tmp_path, "0001")
    names = {p.name for p in image_files(d)}
    # task.json is COPYed in; the Dockerfile itself is build context, not image.
    assert "task.json" in names
    assert "Dockerfile" not in names


def test_scheduling_task_does_not_leak(tmp_path):
    inst = SCHED.generate(3, {"n": 6, "k": 2, "trap": True})
    d = write_task(SCHED, inst, tmp_path, "0001")
    assert audit(d) == []
```

- [ ] **Step 2: Write the audit module**

Create `forge/maf/leak_audit.py`:

```python
"""G1: assert the agent's image contains nothing that derives ground truth.

The audit reads the agent service's Dockerfile COPY directives to decide what
actually lands in the image. Scanning the rendered directory instead would
produce false positives on build-context files (compose files, sidecar
Dockerfiles) that the agent never sees.

Rationale for each marker: shipping generate() lets the agent brute-force the
seed until the public fields match and then read the private ones out of its own
regenerated instance -- which defeats /tests isolation entirely. Shipping ORACLE
lets it execute the reference solution. Shipping verify() lets it read the
grader. All three were executed against the shipped tasks on 2026-07-14.
"""

from __future__ import annotations

import json
from pathlib import Path

# Substrings that must never appear in a file the agent can read.
FORBIDDEN_MARKERS = (
    "def generate(",
    "ORACLE",
    "CHEATERS",
    "def verify(",
    "def ablate(",
    "DIFFICULTY_PRESETS",
)

_SKIP_SUFFIXES = (".pyc",)


def image_files(task_dir: Path) -> list[Path]:
    """Host paths of files copied into the agent image by its Dockerfile."""
    task_dir = Path(task_dir)
    env = task_dir / "environment"
    dockerfile = env / "Dockerfile"
    if not dockerfile.exists():
        return []
    out: list[Path] = []
    for line in dockerfile.read_text().splitlines():
        parts = line.split()
        if len(parts) < 3 or parts[0].upper() != "COPY":
            continue
        src = env / parts[1]
        if src.is_dir():
            out.extend(p for p in src.rglob("*") if p.is_file())
        elif src.is_file():
            out.append(src)
    return [p for p in out if p.suffix not in _SKIP_SUFFIXES]


def _ground_truth_keys(path: Path) -> list[str]:
    if path.suffix != ".json":
        return []
    try:
        data = json.loads(path.read_text())
    except Exception:
        return []
    if not isinstance(data, dict):
        return []
    return [k for k in data if k.startswith("_")]


def audit(task_dir: Path) -> list[str]:
    """Return violations. Empty means the agent image derives no ground truth."""
    task_dir = Path(task_dir)
    violations: list[str] = []
    for f in image_files(task_dir):
        rel = f.relative_to(task_dir)
        for key in _ground_truth_keys(f):
            violations.append(f"{rel}: ground-truth key {key!r} in agent image")
        try:
            text = f.read_text(errors="ignore")
        except Exception:
            continue
        for marker in FORBIDDEN_MARKERS:
            if marker in text:
                violations.append(f"{rel}: grading machinery {marker!r} in agent image")
    return violations
```

- [ ] **Step 3: Run the test to verify the audit correctly reports today's leak**

Run: `.venv/bin/python -m pytest forge/tests/test_leak_audit.py -v`

Expected: `test_image_files_follows_dockerfile_copy` PASSES. `test_scheduling_task_does_not_leak` FAILS, listing `environment/lib/maf_dim.py` violations for `def generate(`, `ORACLE`, `CHEATERS`, `def verify(`, `def ablate(`, `DIFFICULTY_PRESETS`.

This failure is the point: it reproduces audit defects 3 and 4 as an automated red test. Do not fix it here — Task 3 fixes it.

- [ ] **Step 4: Commit the audit with its failing test marked xfail**

Add this decorator to `test_scheduling_task_does_not_leak` so the suite is green while the leak is still open, and Task 3 removes it:

```python
import pytest

@pytest.mark.xfail(reason="leak open until Task 3 relocates the dimension module", strict=True)
def test_scheduling_task_does_not_leak(tmp_path):
    ...
```

```bash
git add forge/maf/leak_audit.py forge/tests/test_leak_audit.py
git commit -m "test(g1): leak audit reproduces the seed-brute-force exploit

audit() reads the agent Dockerfile's COPY directives and reports any
grading machinery or ground-truth key reachable by the agent. Currently
xfail-strict for scheduling: environment/lib/maf_dim.py ships generate(),
which is seed-deterministic and therefore reconstructs /tests content."
```

---

