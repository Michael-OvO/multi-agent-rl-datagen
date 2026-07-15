# Isolation and Gates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop shipping the grading machinery to the agent, prove it with an automated leak audit, and give the validity gates teeth — so that `parallel-scheduling` becomes the first dimension that provably measures its skill.

**Architecture:** The root cause of every verified exploit is `harbor.py:_copy_runtime`, which copies the whole dimension module (generator, oracle, verifier, cheaters) into `environment/lib` and thence into the agent image. Because `generate()` is seed-deterministic, shipping it makes `/tests` isolation decorative. Harbor uploads `tests/` only at verification time (`harbor/verifier/verifier.py:147`, inside `verify()`, which runs after the agent phase), so relocating the module to `tests/lib/` removes it from the agent's reach while keeping the in-container verifier working. This fixes static dimensions completely. Interactive dimensions cannot be fixed this way — their CLI must read the scenario at runtime, inside the agent container — so this plan **quarantines** them and Plan 2 ports them to a sidecar.

**Tech Stack:** Python 3.11+ (stdlib only inside tasks), pytest 8, Harbor 0.18.

## Global Constraints

- Task-side code (anything under a rendered task dir) is **stdlib-only**. No third-party imports.
- `forge/maf/core.py` is copied verbatim into tasks; it must stay stdlib-only.
- Reward shape stays `reward = gate * quality` (`forge/maf/core.py:42`).
- Tests run with `.venv/bin/python -m pytest`.
- Never add Claude as a commit co-author.
- Scope excludes: manifests, `generator_version`, template variation, held-out configs, structural dedup, z3/CSP, random-valid baselines, `reward.json`. These are non-goals per spec §2.

## Out of scope (Plan 2)

The compose sidecar, the `belief-tracking` construct redesign, outcome-based reward for interactive dimensions, and G5 (gradient sweep) all land in Plan 2. This plan quarantines `theory-of-mind` and `failure-recovery` rather than fixing them, because they cannot be fixed without the sidecar.

---

### Task 1: Documentation retraction

`docs/DESIGN.md` claims features that do not exist in `forge/`. Each string below was verified absent. This task is pure removal — no code — and it makes the repo honestly describable immediately.

**Files:**
- Modify: `docs/DESIGN.md`
- Modify: `README.md`
- Test: `forge/tests/test_docs_honesty.py`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing importable. Task 2+ do not depend on this task.

- [ ] **Step 1: Write the failing test**

Create `forge/tests/test_docs_honesty.py`:

```python
"""Docs must not claim capabilities the code does not have.

Every string here was verified absent from forge/ during the 2026-07-14 audit.
If you implement one of these for real, delete its entry -- do not weaken the test.
"""

from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_DESIGN = _ROOT / "docs" / "DESIGN.md"

# (claim, why it is a lie)
UNIMPLEMENTED_CLAIMS = [
    ("z3", "no z3/CSP solver exists in forge/"),
    ("random-valid", "no random-valid baseline exists in forge/"),
    ("liar", "no liar dimension exists in forge/"),
    ("reward.json", "the verifier writes reward.txt, not reward.json"),
    ("held-out", "no held-out config machinery exists in forge/"),
]


@pytest.mark.parametrize("claim,why", UNIMPLEMENTED_CLAIMS)
def test_design_does_not_claim_unimplemented_feature(claim, why):
    text = _DESIGN.read_text().lower()
    assert claim.lower() not in text, f"DESIGN.md claims {claim!r} but {why}"


def test_design_is_not_marked_draft():
    assert "draft for review" not in _DESIGN.read_text().lower()


def test_design_code_fences_are_balanced():
    fences = [ln for ln in _DESIGN.read_text().splitlines() if ln.startswith("```")]
    assert len(fences) % 2 == 0, f"unclosed code fence: {len(fences)} fence markers"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest forge/tests/test_docs_honesty.py -v`

Expected: FAIL. Seven failures — five claim parametrizations, the draft marker, and the fence balance check (DESIGN.md has 13 fence markers).

- [ ] **Step 3: Correct DESIGN.md**

Make these edits:

1. Line 3: replace `**Status:** Draft for review` with `**Status:** Current`.
2. Delete every sentence claiming z3/CSP solving, a random-valid baseline, a liar dimension, `reward.json`, held-out configs, or template variation. Do not reword them into softer claims — delete them.
3. Close the unterminated code fence at end of file (append a line containing exactly ```` ``` ````).
4. Rewrite the "single source of truth" invariant. It currently reads that the dimension module is copied into the task so the in-container verifier grades with the same code the selfcheck validated. That is the root cause of the audit's defects 1, 3, and 4. Replace with:

```markdown
**Isolation invariant.** The dimension module (`generate`, `ORACLE`, `verify`,
`CHEATERS`) never enters the agent's image. Static dimensions ship it to
`tests/lib/`, which Harbor uploads only at verification time. Interactive
dimensions keep it in a sidecar. Identical grading between selfcheck and the
in-container verifier is achieved by shipping the *same file to a place the
agent cannot read* -- not by shipping it to the agent.
```

5. Describe the project as a **deterministic orchestrator microbenchmark forge**. Remove any claim to decomposition or higher-order theory of mind.

- [ ] **Step 4: Correct README.md**

Remove the same claims from `README.md`. Additionally, replace the two `harbor run` examples that reference `tasks/theory-of-mind-0002` with `tasks/parallel-scheduling-0003`, because Task 6 quarantines the interactive dimensions.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest forge/tests/test_docs_honesty.py -v`

Expected: PASS (7 passed).

- [ ] **Step 6: Commit**

```bash
git add docs/DESIGN.md README.md forge/tests/test_docs_honesty.py
git commit -m "docs: retract unimplemented claims; replace copy-into-task invariant

The 'single source of truth' invariant (copy the dimension module into the
task) is the root cause of the ground-truth leak: generate() is
seed-deterministic, so shipping it lets the agent regenerate /tests content.
Replaced with an isolation invariant. Added a test that fails if the docs
re-acquire claims the code does not implement."
```

---

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

### Task 3: Relocate the dimension module out of the agent image

Static dimensions ship `maf_dim.py` to `tests/lib/` instead of `environment/lib/`. Harbor uploads `tests/` inside `verify()` (`harbor/verifier/verifier.py:147`), which runs after the agent phase, so the module is present for grading and absent during the agent's run.

**Files:**
- Modify: `forge/maf/harbor.py:29-53` (`write_task`), `:59-75` (`_write_static`), `:121-130` (`_copy_runtime`)
- Modify: `forge/maf/runtime/verify_entry.py:34` (`sys.path.insert`)
- Modify: `forge/tests/test_leak_audit.py` (drop the xfail)
- Modify: `forge/tests/test_harbor.py:23-30` (`test_public_files_hide_ground_truth`)

**Interfaces:**
- Consumes: `forge.maf.leak_audit.audit` (Task 2).
- Produces: `_copy_runtime(dim, lib_dir: Path, include_cli: bool)` — Plan 2 calls this with the sidecar's lib dir.

- [ ] **Step 1: Strengthen the harbor test that gave false assurance**

`test_public_files_hide_ground_truth` (`forge/tests/test_harbor.py:23`) promises a global property but only runs on scheduling and only checks `instruction.md` and `task.json`. It passed throughout the audit while three exploits were live. Replace it:

```python
from forge.maf.leak_audit import audit


def test_agent_image_hides_ground_truth_and_grader(tmp_path):
    inst = DIM.generate(2, {"n": 5, "k": 2, "trap": True})
    d = write_task(DIM, inst, tmp_path, "0001")
    assert audit(d) == []


def test_dimension_module_ships_to_tests_not_environment(tmp_path):
    inst = DIM.generate(2, {"n": 5, "k": 2, "trap": True})
    d = write_task(DIM, inst, tmp_path, "0001")
    assert (d / "tests" / "lib" / "maf_dim.py").exists()
    assert not (d / "environment" / "lib").exists()
```

- [ ] **Step 2: Run to verify both fail**

Run: `.venv/bin/python -m pytest forge/tests/test_harbor.py -v`

Expected: both new tests FAIL — `audit` returns violations, and `tests/lib/maf_dim.py` does not exist.

- [ ] **Step 3: Relocate the module in `harbor.py`**

In `write_task`, change the directory creation and the `_copy_runtime` call. Replace lines 29-36:

```python
def write_task(dim, instance: dict, out_dir, task_id: str) -> Path:
    task_dir = Path(out_dir) / f"{dim.NAME}-{task_id}"
    for sub in ("environment", "tests/lib", "solution"):
        (task_dir / sub).mkdir(parents=True, exist_ok=True)

    # The dimension module holds generate()/ORACLE/verify()/CHEATERS. It ships to
    # tests/, which Harbor uploads only at verification time -- never to the
    # agent's image. See docs/superpowers/specs/2026-07-14-outcome-based-sidecar-redesign.md
    _copy_runtime(dim, task_dir / "tests" / "lib", include_cli=dim.INTERACTIVE)
```

In `_write_static`, drop the `COPY lib /app/lib` line. Replace lines 62-64:

```python
    (task_dir / "environment" / "Dockerfile").write_text(
        _DOCKER_BASE + "COPY task.json /app/task.json\n"
    )
```

Update `_copy_runtime`'s signature (line 121):

```python
def _copy_runtime(dim, lib_dir: Path, include_cli: bool = False):
    import forge.maf.core as core_mod

    lib_dir.mkdir(parents=True, exist_ok=True)
    lib_dir.joinpath("maf_core.py").write_text(Path(core_mod.__file__).read_text())
    mod = importlib.import_module(type(dim).__module__)
    src = Path(mod.__file__).read_text()
    src = src.replace("from forge.maf.core import", "from maf_core import")
    lib_dir.joinpath("maf_dim.py").write_text(src)
    if include_cli:
        lib_dir.joinpath("cli.py").write_text((_RUNTIME / "cli.py").read_text())
```

- [ ] **Step 4: Point the in-container verifier at the new location**

In `forge/maf/runtime/verify_entry.py`, replace line 34 (`sys.path.insert(0, "/app/lib")`):

```python
    sys.path.insert(0, "/tests/lib")
```

- [ ] **Step 5: Remove the xfail from Task 2's test**

In `forge/tests/test_leak_audit.py`, delete the `@pytest.mark.xfail(...)` decorator and its `import pytest` if now unused.

- [ ] **Step 6: Run the full suite**

Run: `.venv/bin/python -m pytest forge/tests/ -v`

Expected: `test_agent_image_hides_ground_truth_and_grader`, `test_dimension_module_ships_to_tests_not_environment`, and `test_scheduling_task_does_not_leak` all PASS. Interactive-dimension tests still pass (they are in-process and do not render tasks).

- [ ] **Step 7: Prove the exploit is dead end-to-end**

Regenerate a scheduling task and confirm the seed brute-force can no longer run:

```bash
.venv/bin/python -m forge.forge_cli gen --dim parallel-scheduling --seed 3 --difficulty medium --out /tmp/leakcheck
ls /tmp/leakcheck/parallel-scheduling-0000/environment/
```

Expected: `Dockerfile` and `task.json` only. No `lib/`. The generator is not in the image, so there is nothing to brute-force.

- [ ] **Step 8: Commit**

```bash
git add forge/maf/harbor.py forge/maf/runtime/verify_entry.py forge/tests/test_harbor.py forge/tests/test_leak_audit.py
git commit -m "fix(isolation): ship the dimension module to tests/, not the agent image

Harbor uploads tests/ inside verifier.verify(), after the agent phase, so
the module is available for grading and absent during the agent's run.
Closes the seed-brute-force exploit (seed=3 recovered _planted -> 1.0).

Also replaces test_public_files_hide_ground_truth, which promised a global
property, ran only on scheduling, checked only two files, and stayed green
through three live exploits."
```

---

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

### Task 5: Adversarial regression tests

The four executed exploits become permanent tests. Exploits 1, 3, and 4 are now structural (the files are gone), so they assert absence. Exploit 2 (forged submission) is a verifier-contract test and applies to static dimensions now.

**Files:**
- Create: `forge/tests/test_adversarial.py`

**Interfaces:**
- Consumes: `forge.maf.leak_audit.image_files` (Task 2), `forge.maf.harbor.write_task`.
- Produces: nothing importable.

- [ ] **Step 1: Write the tests**

Create `forge/tests/test_adversarial.py`:

```python
"""Regression tests for exploits executed against the shipped tasks on 2026-07-14.

Each test corresponds to an attack that scored reward 1.0 before this plan.
"""

import json

from forge.maf.dimensions.scheduling import DIM
from forge.maf.harbor import write_task
from forge.maf.leak_audit import image_files


def _task(tmp_path):
    inst = DIM.generate(3, {"n": 6, "k": 2, "trap": True})
    return inst, write_task(DIM, inst, tmp_path, "0001")


def test_exploit1_scenario_not_readable_from_agent_image(tmp_path):
    # Attack: cat the scenario out of the image to read the answer.
    _, d = _task(tmp_path)
    for f in image_files(d):
        assert not any(k.startswith("_") for k in _keys(f))


def _keys(path):
    if path.suffix != ".json":
        return []
    try:
        data = json.loads(path.read_text())
    except Exception:
        return []
    return list(data) if isinstance(data, dict) else []


def test_exploit3_oracle_not_present_in_agent_image(tmp_path):
    # Attack: import maf_dim from /app/lib and run the shipped ORACLE.
    _, d = _task(tmp_path)
    for f in image_files(d):
        assert "ORACLE" not in f.read_text(errors="ignore")


def test_exploit4_generator_not_present_in_agent_image(tmp_path):
    # Attack: brute-force the seed against the shipped generate() until the
    # public fields match, then read the private ones. Recovered _planted at
    # seed=3 and scored 1.0.
    _, d = _task(tmp_path)
    for f in image_files(d):
        assert "def generate(" not in f.read_text(errors="ignore")


def test_exploit2_forged_submission_scores_zero(tmp_path):
    # Attack: submit a fabricated artifact instead of doing the work.
    inst, _ = _task(tmp_path)
    forged = [{"subtask": "t0", "worker": "w0", "start": 0}]  # incomplete schedule
    assert DIM.verify(inst, forged).reward == 0.0


def test_empty_submission_scores_zero(tmp_path):
    inst, _ = _task(tmp_path)
    assert DIM.verify(inst, []).reward == 0.0
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest forge/tests/test_adversarial.py -v`

Expected: PASS (5 passed). If any fails, Task 3 is incomplete — do not weaken these tests.

- [ ] **Step 3: Commit**

```bash
git add forge/tests/test_adversarial.py
git commit -m "test: pin the four executed exploits at reward 0

Regression tests for the 2026-07-14 audit: scenario read, oracle execution,
seed brute-force, and forged submission. Each scored 1.0 before this plan."
```

---

### Task 6: Quarantine the interactive dimensions

`theory-of-mind` and `failure-recovery` cannot be fixed by relocating the module: their CLI reads the scenario at runtime, inside the agent container, so the scenario must be in the image. Only the sidecar (Plan 2) fixes them. Until then they must not be renderable, or the forge will keep emitting poisoned data.

**Files:**
- Modify: `forge/forge_cli.py:21-34` (`registry`), `:35-72` (`gen`)
- Test: `forge/tests/test_forge_cli.py`

**Interfaces:**
- Consumes: `registry() -> dict[str, Dimension]` (existing).
- Produces: `forge.forge_cli.QUARANTINED: dict[str, str]` — dimension name to reason. Plan 2 removes entries as it ports each dimension.

- [ ] **Step 1: Write the failing test**

Add to `forge/tests/test_forge_cli.py`:

```python
import pytest

from forge.forge_cli import QUARANTINED, main


def test_quarantined_dimension_cannot_be_rendered(tmp_path):
    with pytest.raises(SystemExit) as exc:
        main(["gen", "--dim", "theory-of-mind", "--out", str(tmp_path)])
    assert exc.value.code != 0
    assert not list(tmp_path.iterdir())


def test_quarantine_names_the_reason():
    assert "theory-of-mind" in QUARANTINED
    assert "failure-recovery" in QUARANTINED
    for reason in QUARANTINED.values():
        assert "sidecar" in reason.lower()
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest forge/tests/test_forge_cli.py -v`

Expected: FAIL with `ImportError: cannot import name 'QUARANTINED'`.

- [ ] **Step 3: Implement the quarantine**

In `forge/forge_cli.py`, add after the imports:

```python
# Dimensions whose CLI must read the scenario at runtime inside the agent
# container, so the scenario is necessarily in the agent's image. Relocating the
# module (as static dimensions do) cannot fix them; only the Plan 2 sidecar can.
# Rendering them would emit data whose reward is obtainable by reading the answer.
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

In `gen`, immediately after resolving `reg = registry()`:

```python
    if args.dim in QUARANTINED:
        raise SystemExit(
            f"refusing to render quarantined dimension {args.dim!r}: "
            f"{QUARANTINED[args.dim]}"
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest forge/tests/test_forge_cli.py -v`

Expected: PASS.

- [ ] **Step 5: Remove the poisoned rendered tasks**

The two rendered interactive tasks in `tasks/` still contain readable ground truth. Delete them:

```bash
git rm -r tasks/theory-of-mind-0002 tasks/failure-recovery-0001
```

- [ ] **Step 6: Commit**

```bash
git add forge/forge_cli.py forge/tests/test_forge_cli.py
git commit -m "feat: quarantine the interactive dimensions until the sidecar lands

theory-of-mind and failure-recovery leak ground truth into the agent image
and cannot be fixed by relocating the module -- their CLI reads the scenario
at runtime inside the agent container. Rendering them emits data whose reward
is obtainable by reading the answer, so the forge now refuses.

Also removes the two rendered tasks, which contain readable ground truth."
```

---

### Task 7: Regenerate scheduling tasks and verify end-to-end

The plan's claims are about generated artifacts, so verify against real ones rather than only unit tests.

**Files:**
- Modify: `tasks/parallel-scheduling-0003/**` (regenerated)

**Interfaces:**
- Consumes: everything above.
- Produces: nothing importable.

- [ ] **Step 1: Regenerate**

```bash
rm -rf tasks/parallel-scheduling-0003
.venv/bin/python -m forge.forge_cli gen --dim parallel-scheduling --seed 3 --difficulty medium --out tasks
```

- [ ] **Step 2: Audit the regenerated task**

```bash
.venv/bin/python -c "
from pathlib import Path
from forge.maf.leak_audit import audit, image_files
d = sorted(Path('tasks').glob('parallel-scheduling-*'))[0]
print('files in agent image:', [str(p.relative_to(d)) for p in image_files(d)])
print('violations:', audit(d))
"
```

Expected: files are `environment/task.json` only; violations is `[]`.

- [ ] **Step 3: Confirm the seed brute-force now fails**

```bash
.venv/bin/python -c "
from pathlib import Path
d = sorted(Path('tasks').glob('parallel-scheduling-*'))[0]
assert not (d / 'environment' / 'lib').exists(), 'lib still in image'
assert (d / 'tests' / 'lib' / 'maf_dim.py').exists(), 'verifier lost its module'
print('generator absent from image; present for the verifier. Exploit 4 is dead.')
"
```

- [ ] **Step 4: Run the task through Harbor with the oracle**

```bash
harbor run --path tasks/parallel-scheduling-0003 --agent oracle -n 1
```

Expected: reward 1.0. This proves relocating the module did not break in-container grading — the verifier finds `maf_dim.py` at `/tests/lib` because Harbor uploads `tests/` before running `test.sh`.

If this fails with `ModuleNotFoundError: maf_dim`, the `sys.path.insert` in Task 3 Step 4 is wrong; check the upload target with `harbor/models/task/paths.py:104`.

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/python -m pytest forge/tests/ -v`

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add tasks/
git commit -m "chore(tasks): regenerate scheduling task without the leak

environment/ now contains task.json only. Verified: harbor run --agent
oracle scores 1.0, so grading still works with the module at /tests/lib."
```

---

## Self-Review

**Spec coverage.** This plan covers spec §7 (Task 1), §6/G1 (Tasks 2, 3), §6/G2 (Task 4), §6 adversarial tests (Task 5), and §8 build steps 1, 2, 5. Spec §3 (sidecar), §4 (outcome-based reward), §5.1 (belief-tracking), §5.2 (silent-failure-recovery), and §6/G5 (gradient) are explicitly deferred to Plan 2 and named in "Out of scope". Spec §6/G3 (ablation) and G4 (cheater panel) already exist as `V3_ablation` and `V1`/`V2` in `forge/maf/selfcheck.py` and need no work — the spec's claim that G3 needs "promoting to a hard gate" was wrong; `V3_ablation` is already inside `ok=all(checks.values())`. The real hole was the cheater panel's coverage, which Task 4 closes.

**Placeholder scan.** No TBD/TODO. Every code step shows complete code. Task 1 Step 3 item 2 says "delete every sentence claiming X" without quoting each sentence — acceptable because the sentences are located by the failing test from Step 1, which names each claim.

**Type consistency.** `audit(task_dir: Path) -> list[str]` and `image_files(task_dir: Path) -> list[Path]` are defined in Task 2 and used with those signatures in Tasks 3, 5, and 7. `_copy_runtime(dim, lib_dir, include_cli=False)` is defined in Task 3 and its `include_cli` parameter is what Plan 2 will use for the sidecar. `QUARANTINED: dict[str, str]` is defined and consumed in Task 6. `DICTATION_CHEATER: str` is defined on the dimension in Task 4 Step 4, read by `selfcheck` in Step 3, and asserted in Step 1's tests; it names a key of `CHEATERS`, never a policy object.

**Corrections made during review.** Two errors were caught by checking the plan's claims against the code rather than trusting them:

1. The draft's `_dictation` policy for scheduling was byte-for-byte identical to the existing `_serial` (`scheduling.py:121-129`). A gate satisfied by duplicating an existing cheater proves nothing. V4 is now a declaration (`DICTATION_CHEATER = "serial"`) rather than a new policy, which also makes the gate's real demand explicit: the author must answer what obeying their own instruction produces.
2. The draft cited `verify_entry.py:38` for the `sys.path.insert`; it is at line 34.

**Known limitation.** Relocating the module to `tests/` relies on Harbor uploading `tests/` only at verification time. An agent that leaves a background process polling for `/tests` to appear could read it during the verifier phase. This is out of scope: it is exotic relative to the LLM reward-hacking threat model, and Plan 2's sidecar removes the exposure for interactive dimensions by keeping the module in a container the agent has no filesystem path to. It is recorded here rather than left unstated.
