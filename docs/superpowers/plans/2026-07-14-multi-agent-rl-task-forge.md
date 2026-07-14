# Multi-Agent RL Task Forge — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `forge` — a pipeline that generates verifiable, clean, construct-valid Harbor RL tasks for three multi-agent orchestration skills (parallel scheduling, failure recovery, theory-of-mind) — plus three oracle-verified sample tasks and a reusable skill.

**Architecture:** All task logic lives once as pure Python in `forge/maf/dimensions/<dim>.py` behind a common **Dimension contract**. The in-process **CLEAN/VALID selfcheck battery** and the in-container **task runtime** both call the same module, so what selfcheck verifies is exactly what ships. `harbor.py` renders a Dimension+instance into a Harbor task directory (copying the module in). Docker is used only for the final `harbor run --agent oracle` smoke-test.

**Tech Stack:** Python 3.11+ (stdlib only for anything that runs in-container), `pytest` for library tests, `uv` for the dev env, Harbor 0.18 (installed) + Docker for the final verification.

## Global Constraints

- **In-container code is stdlib-only.** `environment/` CLIs, `tests/verify.py`, and copied `maf` runtime modules must import only the Python standard library (the task image is `python:3.11-slim`; `test.sh` may `uvx pytest`, but `verify.py` itself is stdlib-only).
- **Determinism.** `generate(seed, difficulty)` is a pure function of its inputs; env responses are pure functions of `scenario.json` + persisted state. No wall-clock, no unseeded RNG (`random.Random(seed)` only).
- **Constructive-generator invariant.** Every generator plants the instance *and* its optimal solution; the oracle replays the planted solution — it never searches at grade time.
- **Public-interface fairness.** The oracle and every cheater interact only through a Dimension's public policy API (the same surface the agent's CLI/artifact uses). They may not read ground-truth fields of the instance.
- **Reward shape.** `reward = gate ∈ {0,1} × quality ∈ (0,1]`, written as a float to `/logs/verifier/reward.txt`; a richer `reward.json` carries sub-scores. Oracle → `1.0`.
- **Ship gate.** A generated instance is written to `tasks/` only if it passes the full CLEAN/VALID battery (§ Task 3). Thresholds: `τ = 0.6` (cheater ceiling), `Δ = 0.4` (min oracle−cheater gap), `ε = 0.05`.
- **No self-authorship in git metadata** (per repo convention): do not add Claude/AI as commit co-author.

## File Structure

```
Kimi-RL-DataGen/
├── README.md                              # overview + run/verify instructions   (Task 10)
├── pyproject.toml                         # dev env (pytest)                      (Task 1)
├── docs/DESIGN.md                         # design doc (exists)
├── forge/
│   ├── maf/
│   │   ├── __init__.py
│   │   ├── core.py                        # RewardBreakdown, reward(), rng, Dimension protocol (Task 1)
│   │   ├── harbor.py                      # render Dimension+instance -> Harbor task dir       (Task 4)
│   │   ├── selfcheck.py                   # CLEAN/VALID battery                                (Task 3)
│   │   ├── runtime/
│   │   │   ├── cli.py                      # generic coord/interview CLI driver (interactive)  (Task 6)
│   │   │   └── verify_entry.py             # generic in-container verify entrypoint            (Task 4)
│   │   └── dimensions/
│   │       ├── scheduling.py              # static, single-shot                                (Task 2)
│   │       ├── failure_recovery.py        # interactive                                        (Task 6)
│   │       └── theory_of_mind.py          # interactive                                        (Task 7)
│   └── forge_cli.py                        # `python -m forge.forge_cli gen ...`               (Task 5)
├── forge/tests/                            # pytest, in-process (no Docker)
│   ├── test_core.py                        (Task 1)
│   ├── test_scheduling.py                  (Task 2)
│   ├── test_selfcheck.py                   (Task 3)
│   ├── test_harbor.py                      (Task 4)
│   ├── test_forge_cli.py                   (Task 5)
│   ├── test_failure_recovery.py            (Task 6)
│   └── test_theory_of_mind.py              (Task 7)
├── tasks/                                  # generated, oracle-verified sample tasks (Task 8)
│   ├── parallel-scheduling-<id>/
│   ├── failure-recovery-<id>/
│   └── theory-of-mind-<id>/
└── skills/multi-agent-task-forge/SKILL.md  # reusable forging skill                (Task 10)
```

### The Dimension contract (defined in Task 1, implemented by every dimension)

```python
# A "policy" is Callable[[Env], None] that drives the env via PUBLIC methods only.
# A "submission" is a JSON-serializable object the verifier grades (schedule list, or transcript).

class Dimension(Protocol):
    NAME: str                                   # e.g. "parallel-scheduling"
    SUBMISSION_FILE: str                        # in-container path agent writes ("schedule.json"
                                                #   for static; "/logs/transcript.jsonl" for interactive)
    INTERACTIVE: bool

    def generate(self, seed: int, difficulty: dict) -> dict: ...          # -> instance (json dict)
    def make_env(self, instance: dict) -> "Env": ...                      # fresh runtime state machine
    def run_policy(self, instance: dict, policy) -> object: ...           # execute policy -> submission
    def verify(self, instance: dict, submission: object) -> RewardBreakdown: ...
    def ablate(self, instance: dict) -> dict: ...                         # skill-removed twin
    def render_instruction(self, instance: dict) -> str: ...             # instruction.md body

    ORACLE: "policy"
    CHEATERS: dict[str, "policy"]               # name -> shortcut policy
```

`RewardBreakdown` (in `core.py`):
```python
@dataclass
class RewardBreakdown:
    reward: float                # gate * quality, in [0,1]
    gate: int                    # 0 or 1
    quality: float               # (0,1]
    subscores: dict              # dimension-specific (e.g. makespan, wasted_dispatches, queries_used)
```

---

## Task 1: Repo scaffold + `maf/core.py`

**Files:**
- Create: `pyproject.toml`, `forge/__init__.py`, `forge/maf/__init__.py`, `forge/maf/dimensions/__init__.py`, `forge/maf/runtime/__init__.py`
- Create: `forge/maf/core.py`
- Test: `forge/tests/test_core.py`

**Interfaces:**
- Produces: `RewardBreakdown` (dataclass above); `reward(gate: int, quality: float, subscores: dict) -> RewardBreakdown` clamping `quality` to `(0,1]` and computing `reward = gate*quality`; `Rng = random.Random`; `transcript_hash(submission) -> str` (stable sha256 of `json.dumps(submission, sort_keys=True)`); the `Dimension`/`Env` `Protocol` definitions.

- [ ] **Step 1: Write the failing test**
```python
# forge/tests/test_core.py
from forge.maf.core import reward, transcript_hash

def test_reward_gate_zero_zeroes_reward():
    rb = reward(gate=0, quality=0.9, subscores={})
    assert rb.reward == 0.0 and rb.gate == 0

def test_reward_gate_one_is_quality():
    rb = reward(gate=1, quality=0.75, subscores={"makespan": 8})
    assert rb.reward == 0.75 and rb.subscores["makespan"] == 8

def test_quality_clamped_to_unit_interval():
    assert reward(1, 1.5, {}).quality == 1.0
    assert reward(1, 0.0, {}).quality > 0.0   # (0,1], never 0 when gate=1

def test_transcript_hash_is_stable_and_order_independent():
    a = transcript_hash({"x": 1, "y": [1, 2]})
    b = transcript_hash({"y": [1, 2], "x": 1})
    assert a == b
```

- [ ] **Step 2: Run test to verify it fails**
Run: `uv run pytest forge/tests/test_core.py -v`
Expected: FAIL (module/functions not defined)

- [ ] **Step 3: Create `pyproject.toml` and scaffold packages**
```toml
# pyproject.toml
[project]
name = "kimi-rl-datagen"
version = "0.1.0"
requires-python = ">=3.11"
[dependency-groups]
dev = ["pytest>=8"]
[tool.pytest.ini_options]
pythonpath = ["."]
```
Create empty `__init__.py` files listed above.

- [ ] **Step 4: Implement `forge/maf/core.py`**
```python
import hashlib, json, random
from dataclasses import dataclass, field
from typing import Protocol, Callable

Rng = random.Random

@dataclass
class RewardBreakdown:
    reward: float
    gate: int
    quality: float
    subscores: dict = field(default_factory=dict)

def reward(gate: int, quality: float, subscores: dict) -> RewardBreakdown:
    q = max(1e-6, min(1.0, float(quality)))
    g = 1 if gate else 0
    return RewardBreakdown(reward=g * q, gate=g, quality=q, subscores=subscores)

def transcript_hash(submission) -> str:
    return hashlib.sha256(json.dumps(submission, sort_keys=True).encode()).hexdigest()

Policy = Callable[["Env"], None]

class Env(Protocol):
    def public_state(self) -> dict: ...     # what the agent may see
    def submission(self) -> object: ...     # graded artifact/transcript

class Dimension(Protocol):
    NAME: str
    SUBMISSION_FILE: str
    INTERACTIVE: bool
    ORACLE: Policy
    CHEATERS: dict
    def generate(self, seed: int, difficulty: dict) -> dict: ...
    def make_env(self, instance: dict) -> Env: ...
    def run_policy(self, instance: dict, policy: Policy) -> object: ...
    def verify(self, instance: dict, submission: object) -> RewardBreakdown: ...
    def ablate(self, instance: dict) -> dict: ...
    def render_instruction(self, instance: dict) -> str: ...
```

- [ ] **Step 5: Run tests to verify they pass**
Run: `uv run pytest forge/tests/test_core.py -v`
Expected: PASS (4 passed)

- [ ] **Step 6: Commit**
```bash
git add pyproject.toml forge/
git commit -m "feat(forge): core reward + Dimension contract"
```

---

## Task 2: `scheduling` dimension (static, single-shot) — the reference dimension

**Files:**
- Create: `forge/maf/dimensions/scheduling.py`
- Test: `forge/tests/test_scheduling.py`

**Interfaces:**
- Consumes: `core.reward`, `core.Rng`.
- Produces a module-level object `DIM` satisfying `Dimension`, plus:
  - `generate(seed, difficulty)` → instance `{"workers": {id: [skills]}, "subtasks": {id: {"skill","dur","deps":[...]}}, "opt_makespan": int, "_planted": [{"subtask","worker","start"}]}` (fields prefixed `_` are ground truth, never shown to the agent).
  - Submission = `list[{"subtask","worker","start"}]`. `SUBMISSION_FILE = "schedule.json"`, `INTERACTIVE = False`.
  - `run_policy(instance, policy)` returns `policy(instance)` (static policies take the *public* instance = instance minus `_`-fields and minus `opt_makespan`).
  - `verify(instance, schedule)`: gate = (every subtask scheduled exactly once ∧ deps: `start ≥ max(dep finish)` ∧ skill match ∧ no worker overlap ∧ valid ids). quality = `opt_makespan / achieved_makespan`. subscores: `{"makespan","opt_makespan"}`.
  - `ORACLE(pub)` → returns `instance["_planted"]` (passed via closure; oracle receives the full instance in `run_policy`). CHEATERS: `serial` (all subtasks on one capable worker, dependency-ordered), `greedy_earliest` (assign each ready task to the capable worker free soonest, tie-break by id), `random_valid` (seeded random valid assignment).
  - `ablate(instance)` removes greedy traps → returns an instance where `serial` achieves `opt_makespan` (used by V3).

**Generation algorithm (constructive — plant the optimum):**
1. Choose `k` workers, horizon `T`, from `difficulty`.
2. Lay out a random *valid* schedule of `n` subtasks on the `k×T` grid: pick durations, assign each to a worker/time slot with no overlap; derive `deps` from grid order within a chain + some cross-worker edges that respect time (a dep edge `u→v` only if `finish(u) ≤ start(v)`). Assign each subtask a `skill`; give each worker a skill set that *covers its assigned tasks* plus controlled extra coverage (capability scarcity knob).
3. `opt_makespan = max finish over the planted layout` (known-optimal because every subtask's earliest possible start is bounded by its dependency chain and the layout achieves it — assert no schedule can beat it via a critical-path lower bound check).
4. **Plant a greedy trap** (difficulty ≥ medium): make one scarce worker (only tester) *also* capable of a code task so that `greedy_earliest` grabs it early and delays the bottleneck; assert `verify(instance, greedy_earliest(pub)).reward < 1.0` at generation (the generator retries seeds until the trap bites).

- [ ] **Step 1: Write failing tests**
```python
# forge/tests/test_scheduling.py
from forge.maf.dimensions.scheduling import DIM

def test_oracle_scores_one_across_seeds():
    for seed in range(20):
        inst = DIM.generate(seed, {"n": 6, "k": 3, "trap": True})
        sub = DIM.run_policy(inst, DIM.ORACLE)
        assert DIM.verify(inst, sub).reward == 1.0

def test_verify_rejects_dependency_violation():
    inst = DIM.generate(1, {"n": 4, "k": 2, "trap": False})
    bad = DIM.run_policy(inst, DIM.ORACLE)
    bad[-1]["start"] = 0  # force a dependent task to start at 0
    assert DIM.verify(inst, bad).gate == 0

def test_serial_cheater_is_suboptimal_on_trap():
    inst = DIM.generate(3, {"n": 6, "k": 3, "trap": True})
    r = DIM.verify(inst, DIM.run_policy(inst, DIM.CHEATERS["serial"]))
    assert r.reward < 1.0

def test_ablation_makes_serial_optimal():
    inst = DIM.generate(3, {"n": 6, "k": 3, "trap": True})
    twin = DIM.ablate(inst)
    r = DIM.verify(twin, DIM.run_policy(twin, DIM.CHEATERS["serial"]))
    assert r.reward >= 0.95

def test_generation_is_deterministic():
    assert DIM.generate(7, {"n": 6, "k": 3}) == DIM.generate(7, {"n": 6, "k": 3})
```

- [ ] **Step 2: Run to verify fail** — `uv run pytest forge/tests/test_scheduling.py -v` → FAIL.
- [ ] **Step 3: Implement `scheduling.py`** per the algorithm and interfaces above. Verifier is stdlib-only. Keep `_planted`/`opt_makespan` out of the public instance via a `public(instance)` helper that strips `_`-prefixed keys and `opt_makespan`.
- [ ] **Step 4: Run to verify pass** — Expected: 5 passed. If `test_serial_cheater_is_suboptimal_on_trap` fails, the trap planting is wrong — fix the generator's retry-until-trap-bites loop.
- [ ] **Step 5: Commit** — `git commit -m "feat(forge): scheduling dimension with constructive generator + trap"`

---

## Task 3: CLEAN/VALID selfcheck battery

**Files:**
- Create: `forge/maf/selfcheck.py`
- Test: `forge/tests/test_selfcheck.py`

**Interfaces:**
- Consumes: a `Dimension` + an instance.
- Produces: `selfcheck(dim, instance, tau=0.6, delta=0.4, eps=0.05) -> SelfcheckReport` with `.ok: bool` and `.checks: dict[str,bool]` and `.detail: dict`. Checks: `C1_determinism, C2_solvable_fair, C3_unique, C4_verifier_robust, C5_wellposed, V1_cheaters_lose, V2_discrimination, V3_ablation`.

**Check implementations:**
- **C1**: run oracle twice; `transcript_hash(sub1)==transcript_hash(sub2)` and equal reward.
- **C2**: `verify(inst, run_policy(inst, ORACLE)).reward == 1.0`. (Fairness is structural: policies get only `public(inst)` / the Env's public surface — enforced in each dimension's `run_policy`.)
- **C3**: dimension exposes `unique_ground_truth(inst) -> bool` (scheduling: `opt_makespan` matches the critical-path/resource lower bound; ToM: exactly one satisfying assignment by enumeration). Battery calls it; default `True` where N/A.
- **C4**: feed `verify` a set of malformed submissions (`None`, `[]`, `[{"subtask":"nope"}]`, `"garbage"`); assert each returns a `RewardBreakdown` with `0 ≤ reward ≤ 1` and no exception.
- **C5**: a `format_only` submission (well-formed shape, wrong content) → `gate==0` (or reward 0), no crash.
- **V1**: for each cheater, `verify(inst, run_policy(inst, cheater)).reward < tau`.
- **V2**: `oracle_reward - max(cheater_rewards) > delta`.
- **V3**: `twin = ablate(inst)`; at least one cheater scores `≥ 1 - eps` on the twin.

- [ ] **Step 1: Write failing tests**
```python
# forge/tests/test_selfcheck.py
from forge.maf.dimensions.scheduling import DIM
from forge.maf.selfcheck import selfcheck

def test_good_scheduling_instance_passes_all():
    inst = DIM.generate(3, {"n": 6, "k": 3, "trap": True})
    rep = selfcheck(DIM, inst)
    assert rep.ok, rep.checks

def test_trivial_instance_fails_validity():
    inst = DIM.generate(3, {"n": 6, "k": 3, "trap": True})
    trivial = DIM.ablate(inst)               # serial == optimal here
    rep = selfcheck(DIM, trivial)
    assert not rep.ok
    assert rep.checks["V1_cheaters_lose"] is False or rep.checks["V2_discrimination"] is False

def test_c4_robust_to_garbage():
    inst = DIM.generate(1, {"n": 4, "k": 2})
    rep = selfcheck(DIM, inst)
    assert rep.checks["C4_verifier_robust"] is True
```

- [ ] **Step 2: Run to verify fail** → FAIL.
- [ ] **Step 3: Implement `selfcheck.py`** per the checks above.
- [ ] **Step 4: Run to verify pass** — Expected: 3 passed.
- [ ] **Step 5: Commit** — `git commit -m "feat(forge): CLEAN/VALID selfcheck battery"`

---

## Task 4: `harbor.py` — render a Dimension+instance into a Harbor task dir

**Files:**
- Create: `forge/maf/harbor.py`, `forge/maf/runtime/verify_entry.py`
- Test: `forge/tests/test_harbor.py`

**Interfaces:**
- Consumes: `Dimension`, instance, `selfcheck` (optional gate).
- Produces: `write_task(dim, instance, out_dir, task_id) -> Path` that writes the full Harbor tree:
  - `task.toml` (schema_version "1.3"; name `demo/<NAME>-<id>`; `[verifier] timeout_sec`; `[environment]` image built from Dockerfile; standard metadata).
  - `instruction.md` = `dim.render_instruction(public(instance))` + a fixed "Output contract" section (schema of `SUBMISSION_FILE` / CLI usage).
  - `environment/Dockerfile` (`FROM python:3.11-slim`, `WORKDIR /app`, copy `scenario.json` + `lib/`, and for interactive dims install the `coord`/`interview` CLI on PATH).
  - `environment/scenario.json` = `json.dumps(instance)` (full instance; ground-truth `_`-fields live here but are only read by `verify.py`, never exposed by the CLI/instruction).
  - `environment/lib/maf_core.py`, `environment/lib/maf_dim.py` = copies of `core.py` and the dimension module (single source of truth copied in).
  - `tests/test.sh` (installs pytest via uvx, runs `verify.py`, writes reward.txt from its exit/print) and `tests/verify.py` (imports copied `maf_dim`, loads submission from `SUBMISSION_FILE`, calls `verify`, prints reward, writes `/logs/verifier/reward.json`).
  - `solution/solve.sh` = oracle: for static, run the planted solver and write `schedule.json`; for interactive, run `runtime/cli.py`-driving oracle script. Uses only the public interface.

- [ ] **Step 1: Write failing test**
```python
# forge/tests/test_harbor.py
import json, tomllib, subprocess, sys
from pathlib import Path
from forge.maf.dimensions.scheduling import DIM
from forge.maf.harbor import write_task

def test_write_task_produces_valid_tree(tmp_path):
    inst = DIM.generate(2, {"n": 5, "k": 2})
    d = write_task(DIM, inst, tmp_path, "0001")
    assert (d / "task.toml").exists()
    tomllib.loads((d / "task.toml").read_text())          # parses
    assert (d / "instruction.md").read_text().strip()
    assert (d / "environment" / "scenario.json").exists()
    assert (d / "solution" / "solve.sh").exists()
    assert (d / "tests" / "verify.py").exists()

def test_instruction_hides_ground_truth(tmp_path):
    inst = DIM.generate(2, {"n": 5, "k": 2})
    d = write_task(DIM, inst, tmp_path, "0001")
    text = (d / "instruction.md").read_text()
    assert "opt_makespan" not in text and "_planted" not in text

def test_oracle_solution_verifies_in_process(tmp_path):
    # emulate: run solve to produce submission, then verify.py logic, assert reward 1.0
    inst = DIM.generate(2, {"n": 5, "k": 2})
    sub = DIM.run_policy(inst, DIM.ORACLE)
    assert DIM.verify(inst, sub).reward == 1.0
```

- [ ] **Step 2: Run to verify fail** → FAIL.
- [ ] **Step 3: Implement `harbor.py` + `verify_entry.py`.** Keep templates as string constants. `verify.py` and copied modules stdlib-only.
- [ ] **Step 4: Run to verify pass** — Expected: 3 passed.
- [ ] **Step 5: Commit** — `git commit -m "feat(forge): Harbor task renderer"`

---

## Task 5: `forge_cli.py` — generate + gate + write

**Files:**
- Create: `forge/forge_cli.py`
- Test: `forge/tests/test_forge_cli.py`

**Interfaces:**
- Produces CLI: `python -m forge.forge_cli gen --dim parallel-scheduling --seed 0 --n 3 --difficulty medium --out tasks/` → for each of `n` seeds, `generate`, run `selfcheck`; if `.ok`, `write_task` into `out`; else log and skip. Prints a summary `{"requested": n, "shipped": m, "rejected": [...]}`. A `--difficulty` name maps to a preset dict (`easy/medium/hard`) held in each dimension (`DIM.DIFFICULTY_PRESETS`).

- [ ] **Step 1: Write failing test**
```python
# forge/tests/test_forge_cli.py
import subprocess, sys, json
from pathlib import Path

def test_cli_ships_only_passing_tasks(tmp_path):
    out = tmp_path / "tasks"
    r = subprocess.run([sys.executable, "-m", "forge.forge_cli", "gen",
                        "--dim", "parallel-scheduling", "--seed", "0", "--n", "3",
                        "--difficulty", "medium", "--out", str(out)],
                       capture_output=True, text=True, cwd=".")
    assert r.returncode == 0, r.stderr
    dirs = list(out.glob("parallel-scheduling-*"))
    assert len(dirs) >= 1
    for d in dirs:
        assert (d / "task.toml").exists()
```

- [ ] **Step 2: Run to verify fail** → FAIL.
- [ ] **Step 3: Implement `forge_cli.py`** (argparse; registry mapping dim name → module `DIM`).
- [ ] **Step 4: Run to verify pass** — Expected: 1 passed.
- [ ] **Step 5: Commit** — `git commit -m "feat(forge): generation CLI with ship gate"`

---

## Task 6: `failure_recovery` dimension (interactive) + generic CLI runtime

**Files:**
- Create: `forge/maf/dimensions/failure_recovery.py`, `forge/maf/runtime/cli.py`
- Test: `forge/tests/test_failure_recovery.py`

**Interfaces:**
- `make_env(instance)` → `Env` with public methods `roster()`, `dag()`, `dispatch(task, worker) -> {"result": "SUCCESS"|"FAILURE", "reason": str}`, `status()`, `submit()`; persists nothing hidden. Instance ground truth: `_success[(task,worker)] -> bool`, decoys, silent-failure edges, `_budget`. `SUBMISSION_FILE = "/logs/transcript.jsonl"`, `INTERACTIVE = True`.
- `run_policy(instance, policy)`: builds env, runs policy (issues public calls), returns the recorded transcript (list of interactions incl. final `status`).
- `verify(instance, transcript)`: gate = all subtasks SUCCESS at submit ∧ protocol compliance (no dispatch before deps complete) ∧ within budget. quality = `1 - wasted_dispatches / budget`. subscores: `{"wasted_dispatches","budget","dispatches"}`.
- `ORACLE`: try each capable worker in id order, on FAILURE try next, respect deps. CHEATERS: `static_plan` (dispatch each task to its first rostered worker once, never react), `retry_same` (retry the first worker up to budget), `brute_force` (dispatch every task to every worker).
- `ablate(instance)`: set all `_success=True` (no failures) → `static_plan` completes → scores 1.0.
- `runtime/cli.py`: a generic driver that, given `--dim` and a command, loads `scenario.json` + `/logs/state.json`, applies one public method, appends to `/logs/transcript.jsonl`, prints the public response. The task's `coord` is a 2-line shim calling `cli.py`.

- [ ] **Step 1: Write failing tests**
```python
# forge/tests/test_failure_recovery.py
from forge.maf.dimensions.failure_recovery import DIM
from forge.maf.selfcheck import selfcheck

def test_oracle_completes_and_scores_one():
    for s in range(20):
        inst = DIM.generate(s, {"n": 5, "workers": 3, "fail_rate": 0.3})
        assert DIM.verify(inst, DIM.run_policy(inst, DIM.ORACLE)).reward == 1.0

def test_static_plan_fails_when_failures_present():
    inst = DIM.generate(0, {"n": 5, "workers": 3, "fail_rate": 0.4})
    assert DIM.verify(inst, DIM.run_policy(inst, DIM.CHEATERS["static_plan"])).reward < 0.6

def test_brute_force_exhausts_budget():
    inst = DIM.generate(0, {"n": 5, "workers": 3, "fail_rate": 0.4})
    assert DIM.verify(inst, DIM.run_policy(inst, DIM.CHEATERS["brute_force"])).reward < 0.6

def test_selfcheck_passes():
    inst = DIM.generate(1, {"n": 5, "workers": 3, "fail_rate": 0.3})
    assert selfcheck(DIM, inst).ok

def test_ablation_static_plan_wins():
    inst = DIM.generate(1, {"n": 5, "workers": 3, "fail_rate": 0.3})
    twin = DIM.ablate(inst)
    assert DIM.verify(twin, DIM.run_policy(twin, DIM.CHEATERS["static_plan"])).reward >= 0.95
```

- [ ] **Step 2: Run to verify fail** → FAIL.
- [ ] **Step 3: Implement dimension + `cli.py`.** Guarantee ≥1 feasible assignment at generation; set `_budget ≥ oracle dispatch count` (so oracle fits) but `< workers*subtasks` (so brute force exhausts).
- [ ] **Step 4: Run to verify pass** — Expected: 5 passed.
- [ ] **Step 5: Commit** — `git commit -m "feat(forge): failure-recovery dimension + interactive CLI runtime"`

---

## Task 7: `theory_of_mind` dimension (interactive)

**Files:**
- Create: `forge/maf/dimensions/theory_of_mind.py`
- Test: `forge/tests/test_theory_of_mind.py`

**Interfaces:**
- Instance: a small logic puzzle (suspects × attributes) with a **unique** solution (verified by enumeration over the finite space), clues **partitioned** across agents' private knowledge, a **referral graph** (agent A knows "ask B about topic t"), and `_budget < exhaustive`.
- `make_env` public methods: `agents()`, `ask(agent, topic) -> {"info": str|None, "referral": agent|None}`, `submit(answer) -> {"correct": bool}`. `SUBMISSION_FILE = "/logs/transcript.jsonl"`, `INTERACTIVE = True`.
- `verify(instance, transcript)`: gate = correct answer submitted. quality = `1 - queries_used / budget` (targeted querying rewarded). subscores: `{"queries_used","budget"}`.
- `ORACLE`: follow referrals from the seed agents, gather the minimal clue set, deduce, submit. CHEATERS: `info_dump` (ask agents/topics in fixed order until budget, then guess best), `random_target`, `no_referral` (never follow a referral).
- `ablate(instance)`: make every clue public from every agent (kill asymmetry) → any direct read within budget solves → `info_dump` scores ≥ 0.95.
- `unique_ground_truth(instance)`: enumerate; assert exactly one satisfying assignment.

- [ ] **Step 1: Write failing tests**
```python
# forge/tests/test_theory_of_mind.py
from forge.maf.dimensions.theory_of_mind import DIM
from forge.maf.selfcheck import selfcheck

def test_unique_solution():
    for s in range(20):
        inst = DIM.generate(s, {"suspects": 4, "clues": 4, "referral_depth": 2})
        assert DIM.unique_ground_truth(inst)

def test_oracle_solves_within_budget():
    for s in range(20):
        inst = DIM.generate(s, {"suspects": 4, "clues": 4, "referral_depth": 2})
        assert DIM.verify(inst, DIM.run_policy(inst, DIM.ORACLE)).reward == 1.0

def test_info_dump_cannot_win_under_budget():
    inst = DIM.generate(0, {"suspects": 4, "clues": 4, "referral_depth": 2})
    assert DIM.verify(inst, DIM.run_policy(inst, DIM.CHEATERS["info_dump"])).reward < 0.6

def test_selfcheck_passes():
    inst = DIM.generate(2, {"suspects": 4, "clues": 4, "referral_depth": 2})
    assert selfcheck(DIM, inst).ok

def test_ablation_direct_read_wins():
    inst = DIM.generate(2, {"suspects": 4, "clues": 4, "referral_depth": 2})
    twin = DIM.ablate(inst)
    assert DIM.verify(twin, DIM.run_policy(twin, DIM.CHEATERS["info_dump"])).reward >= 0.95
```

- [ ] **Step 2: Run to verify fail** → FAIL.
- [ ] **Step 3: Implement dimension.** Generate solution first, then clues that uniquely pin it; partition clues; build referral graph so a minimal query path exists; set budget between the oracle's query count and exhaustive.
- [ ] **Step 4: Run to verify pass** — Expected: 5 passed.
- [ ] **Step 5: Commit** — `git commit -m "feat(forge): theory-of-mind dimension"`

---

## Task 8: Generate the 3 sample tasks + Docker oracle verification

**Files:**
- Create (generated): `tasks/parallel-scheduling-<id>/`, `tasks/failure-recovery-<id>/`, `tasks/theory-of-mind-<id>/`
- Create: `scripts/verify_all.sh`

**Preconditions:** Docker daemon running (`open -a Docker`; wait for `docker info` to succeed).

- [ ] **Step 1: Generate one task per dimension**
```bash
uv run python -m forge.forge_cli gen --dim parallel-scheduling --seed 3 --n 1 --difficulty medium --out tasks/
uv run python -m forge.forge_cli gen --dim failure-recovery   --seed 1 --n 1 --difficulty medium --out tasks/
uv run python -m forge.forge_cli gen --dim theory-of-mind     --seed 2 --n 1 --difficulty medium --out tasks/
```
Expected: each prints `shipped: 1`.

- [ ] **Step 2: Write `scripts/verify_all.sh`**
```bash
#!/usr/bin/env bash
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
for t in tasks/parallel-scheduling-* tasks/failure-recovery-* tasks/theory-of-mind-*; do
  echo "=== oracle: $t ==="
  harbor run --path "$t" --agent oracle -n 1
done
```

- [ ] **Step 3: Run oracle verification (Docker)**
Run: `bash scripts/verify_all.sh`
Expected: each task reports reward `1.0`. (Resolve the exact `harbor run` local-path invocation against `harbor run --help` if `--path` differs in 0.18; fall back to `harbor exec -p <task>`.)

- [ ] **Step 4: Commit** — `git add tasks scripts && git commit -m "feat(tasks): 3 oracle-verified sample tasks"`

---

## Task 9: Real `claude-code` run — demonstrate partial-reward signal

**Preconditions:** `ANTHROPIC_API_KEY` set; Docker running.

- [ ] **Step 1: Run a real agent on each task**
```bash
export ANTHROPIC_API_KEY=...   # user-provided
for t in tasks/parallel-scheduling-* tasks/failure-recovery-* tasks/theory-of-mind-*; do
  harbor run --path "$t" --agent claude-code --model anthropic/claude-opus-4-1 -n 1
done
```
- [ ] **Step 2: Capture rewards** into `docs/RESULTS.md` (oracle=1.0 vs claude-code partial), demonstrating the reward spread the RL signal needs.
- [ ] **Step 3: Commit** — `git commit -m "docs: real-agent partial-reward results"`

---

## Task 10: Skill + README + polish

**Files:**
- Create: `skills/multi-agent-task-forge/SKILL.md`, `README.md`

- [ ] **Step 1: Write `skills/multi-agent-task-forge/SKILL.md`** documenting: the Dimension contract, the CLEAN/VALID invariants, the constructive-generator rule, and a checklist for adding a new dimension (define public API, plant optimum, write cheater panel + ablation, pass selfcheck).
- [ ] **Step 2: Write `README.md`**: what this is, layout, `uv run pytest` to test the library, `forge_cli` usage, `scripts/verify_all.sh` to Docker-verify, pointer to `docs/DESIGN.md`.
- [ ] **Step 3: Run full test suite** — `uv run pytest forge/tests -v` → all pass.
- [ ] **Step 4: Commit** — `git commit -m "docs: skill + README"`

---

## Self-Review notes

- **Spec coverage:** capability spine → dimensions (Tasks 2/6/7); env-as-verifier → `make_env`+`verify`; CLEAN/VALID battery §4.3 → Task 3; constructive-oracle invariant → Task 2/6/7 generation; scale/`forge` §9 → Task 5; deliverables §10 → Tasks 8–10. Topology/Sub↔Sub deferred (documented in DESIGN §2.4), no task — intentional.
- **Determinism** enforced by `random.Random(seed)` only; C1 checks it.
- **Type consistency:** `Dimension`/`RewardBreakdown`/`Policy` defined once in Task 1 and referenced verbatim thereafter; `run_policy`/`verify`/`ablate`/`generate` signatures identical across dimensions.
- **Docker-gated tasks (8,9)** are the only ones needing the daemon; all library tasks (1–7) run purely in-process.
