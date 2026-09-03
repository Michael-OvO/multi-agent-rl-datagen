# Harbor as the Single Shipped Form — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every cell of the Gaia2 campaign grid is rendered as a Harbor task by the campaign itself, deterministically, tracked in git, and a task that lags the runtime fails the test suite.

**Architecture:** The renderer (`forge/gaia2/harbor.py`) becomes deterministic (derived token, write-if-changed, a provenance file with a content digest of the shipped runtime). The grid definition moves out of the campaign script into `forge/gaia2/grid.py` so the campaign, the render command and a drift test share it. The campaign renders every cell before running any; a new test walks `tasks/MANIFEST.json`. The viewer index reads provenance and links each Gaia2 task to its campaign trajectories.

**Tech Stack:** Python 3.11, pytest, ruff; the viewer is one HTML file with vanilla JavaScript; JavaScriptCore via `osascript` for the parse check.

Spec: `docs/superpowers/specs/2026-09-03-harbor-single-form-design.md`.

## Global Constraints

- Work in the worktree `/Users/michael/Documents/Github/multi-agent-rl-datagen/.claude/worktrees/harbor-single-form` on branch `worktree-harbor-single-form`. Never `cd` to, edit, or merge into the main checkout `/Users/michael/Documents/Github/multi-agent-rl-datagen` while the v7 campaign runs there.
- Tests: `/Users/michael/Documents/Github/multi-agent-rl-datagen/.venv/bin/python -m pytest -q -p no:cacheprovider` run from the worktree root. Call this interpreter `$PY` below: `PY=/Users/michael/Documents/Github/multi-agent-rl-datagen/.venv/bin/python`.
- Lint: `$PY -m ruff check forge scripts` must report no errors (rules E4, E7, E9, F, B, I).
- Nothing that imports `are.*` (`forge/gaia2/are_world.py`, `scripts/gaia2_cell_run.py` below its argparse) is imported by any test or by `forge/gaia2/harbor.py`, `forge/gaia2/grid.py`, `forge/gaia2/cli.py`, or `scripts/embed_logs.py`.
- Token derivation is exactly `hashlib.sha256(f"{scenario_id}|{label}|{OBJECTIVE_ACTION_CONTRACT_VERSION}|{JUDGE_PARSE_VERSION}".encode()).hexdigest()[:32]`.
- A task's name is exactly `gaia2-{constraints.label}-{scenario_id}`; the control cell's label is `open-docs-binf`.
- `tasks/MANIFEST.json` is a JSON list of `{"name", "scenario_id", "config", "soft_judge"}` sorted by `name`, written with `indent=1` and a trailing newline.
- `provenance.json` at a task's root has exactly the keys `scenario_id`, `config`, `objective_action_contract`, `judge_parse`, `runtime_digest`.
- The renderer writes a file only when its bytes would change.
- `--dry-run` on the campaign renders nothing and returns before `try_refresh`.
- Viewer: badges are built only by `badge(kind, label)`; no new `--` CSS tokens; the page stays one self-contained file; every change must pass the JavaScriptCore parse check in Task 7.
- Nothing under `forge/appworld/`, `tasks/appworld-*`, `tasks/parallel-scheduling-0003`, `jobs/` or `sweep/appworld_*` changes.
- Moved code is moved, not rewritten: `eligible` and `scenario_paths` in Task 2 keep their bodies and docstrings byte-for-byte apart from the `root` parameter.
- Commit after every task with `git add <named files>`; never `git add -A`.

---

## File map

| File | Responsibility after this plan |
|---|---|
| `forge/gaia2/harbor.py` | render one task (`write_task`), deterministic token (`derive_token`), runtime content digest (`runtime_digest`), write-if-changed (`_put`), `provenance`, `render_grid`, `write_manifest` |
| `forge/gaia2/grid.py` (new) | `Cell`, `GRID`, `eligible`, `scenario_paths`, `cells_for`, `cells` — the grid in one place |
| `forge/gaia2/cli.py` | `render --scenario` (four cells, derived token) and `render --all` (grid + manifest) |
| `scripts/gaia2_campaign.py` | builds jobs from `cells()`; renders the grid before running |
| `forge/tests/test_gaia2_harbor.py` | renderer tests (extended) |
| `forge/tests/test_gaia2_grid.py` (new) | grid tests |
| `forge/tests/test_gaia2_cli.py` (new) | render command tests |
| `forge/tests/test_gaia2_campaign.py` | campaign source-order tests (extended; `eligible` import repointed) |
| `forge/tests/test_gaia2_tasks_current.py` (new) | the drift guard over `tasks/` |
| `tasks/gaia2-*`, `tasks/MANIFEST.json` | the rendered grid, 132 tasks |
| `scripts/embed_logs.py` | task records carry provenance and campaign links |
| `forge/tests/test_embed_logs.py` | index tests (extended) |
| `trajectory_viewer.html` | Tasks view: substrate filter, campaigns, stale badge |
| `DESIGN.md`, `README.md`, `PRODUCT.md` | the record follows |

---

### Task 1: Deterministic renderer

**Files:**
- Modify: `forge/gaia2/harbor.py` (imports at lines 28-35; `write_task` at lines 178-232)
- Test: `forge/tests/test_gaia2_harbor.py`

**Interfaces:**
- Consumes: `OBJECTIVE_ACTION_CONTRACT_VERSION` from `forge.gaia2.runtime`; `JUDGE_PARSE_VERSION` from `forge.gaia2.judge_parse`; `VERBATIM_COPIES` (existing dict in this file).
- Produces: `derive_token(scenario_id: str, label: str) -> str`; `runtime_digest() -> str`; `_put(path: Path, text: str) -> bool`; `provenance(scenario_id: str, constraints: Constraints) -> dict`; `write_task` unchanged in signature, now writing `provenance.json` and rewriting only changed bytes.

- [ ] **Step 1: Make the worktree able to render real scenarios (one-time setup)**

The dataset is git-ignored, so the worktree has none. Link the main checkout's copy; the path is ignored, so the link is never committed.

```bash
cd /Users/michael/Documents/Github/multi-agent-rl-datagen/.claude/worktrees/harbor-single-form
ln -s /Users/michael/Documents/Github/multi-agent-rl-datagen/gaia2_data gaia2_data
git status --short | grep gaia2_data || echo "link is ignored, as required"
```

Expected: the second line prints `link is ignored, as required`.

- [ ] **Step 2: Write the failing tests**

Append to `forge/tests/test_gaia2_harbor.py`:

```python
# -- deterministic renders --------------------------------------------------

from forge.gaia2.harbor import (  # noqa: E402
    _put,
    derive_token,
    provenance,
    runtime_digest,
)
from forge.gaia2.judge_parse import JUDGE_PARSE_VERSION  # noqa: E402

FAKE_SCENARIO = '{"scenario_id": "scenario_fake_1", "events": []}\n'


def _fake_scenario(tmp_path):
    p = tmp_path / "scenario_fake_1.json"
    p.write_text(FAKE_SCENARIO)
    return p


def test_the_token_is_a_function_of_cell_and_versions_only():
    a = derive_token("scenario_x", "star-docs-binf")
    assert a == derive_token("scenario_x", "star-docs-binf")
    assert re.fullmatch(r"[0-9a-f]{32}", a)
    assert a != derive_token("scenario_y", "star-docs-binf")
    assert a != derive_token("scenario_x", "star-names-binf")
    seed = (f"scenario_x|star-docs-binf|{OBJECTIVE_ACTION_CONTRACT_VERSION}"
            f"|{JUDGE_PARSE_VERSION}")
    import hashlib
    assert a == hashlib.sha256(seed.encode()).hexdigest()[:32]


def test_the_runtime_digest_covers_every_verbatim_source(monkeypatch, tmp_path):
    before = runtime_digest()
    assert re.fullmatch(r"[0-9a-f]{64}", before)
    assert before == runtime_digest()
    # Change one shipped source and the digest moves.
    dest, src = next(iter(VERBATIM_COPIES.items()))
    fake = tmp_path / "changed.txt"
    fake.write_text(src.read_text() + "\n# changed\n")
    monkeypatch.setitem(VERBATIM_COPIES, dest, fake)
    assert runtime_digest() != before


def test_put_writes_only_when_bytes_differ(tmp_path):
    p = tmp_path / "sub" / "f.txt"
    assert _put(p, "one\n") is True
    stamp = p.stat().st_mtime_ns
    assert _put(p, "one\n") is False
    assert p.stat().st_mtime_ns == stamp
    assert _put(p, "two\n") is True
    assert p.read_text() == "two\n"


def test_a_render_writes_provenance_with_exactly_the_five_keys(tmp_path):
    scen = _fake_scenario(tmp_path)
    task = write_task(scen, "scenario_fake_1", C, tmp_path / "out",
                      token=derive_token("scenario_fake_1", C.label))
    prov = json.loads((task / "provenance.json").read_text())
    assert prov == {
        "scenario_id": "scenario_fake_1",
        "config": C.label,
        "objective_action_contract": OBJECTIVE_ACTION_CONTRACT_VERSION,
        "judge_parse": JUDGE_PARSE_VERSION,
        "runtime_digest": runtime_digest(),
    }
    assert prov == provenance("scenario_fake_1", C)


def test_a_second_render_of_the_same_cell_rewrites_nothing(tmp_path):
    scen = _fake_scenario(tmp_path)
    token = derive_token("scenario_fake_1", C.label)
    task = write_task(scen, "scenario_fake_1", C, tmp_path / "out", token=token)
    stamps = {p: p.stat().st_mtime_ns for p in task.rglob("*") if p.is_file()}
    assert len(stamps) > 10
    write_task(scen, "scenario_fake_1", C, tmp_path / "out", token=token)
    after = {p: p.stat().st_mtime_ns for p in task.rglob("*") if p.is_file()}
    assert after == stamps


def test_a_render_after_a_runtime_change_touches_only_what_changed(tmp_path, monkeypatch):
    scen = _fake_scenario(tmp_path)
    token = derive_token("scenario_fake_1", C.label)
    task = write_task(scen, "scenario_fake_1", C, tmp_path / "out", token=token)
    stamps = {p: p.stat().st_mtime_ns for p in task.rglob("*") if p.is_file()}
    dest = "environment/server.py"
    fake = tmp_path / "server_changed.py"
    fake.write_text(VERBATIM_COPIES[dest].read_text() + "\n# changed\n")
    monkeypatch.setitem(VERBATIM_COPIES, dest, fake)
    write_task(scen, "scenario_fake_1", C, tmp_path / "out", token=token)
    changed = {p.relative_to(task).as_posix()
               for p, t in stamps.items() if p.stat().st_mtime_ns != t}
    assert changed == {"environment/server.py", "provenance.json"}
```

`json`, `re`, `Path`, `C`, `write_task`, `VERBATIM_COPIES`, `OBJECTIVE_ACTION_CONTRACT_VERSION` are already imported at the top of that file; keep the new imports at the bottom with `# noqa: E402` as shown so the existing top block is untouched.

- [ ] **Step 3: Run the tests to verify they fail**

Run: `$PY -m pytest forge/tests/test_gaia2_harbor.py -q -p no:cacheprovider`
Expected: ImportError on `_put`, `derive_token`, `provenance`, `runtime_digest`.

- [ ] **Step 4: Implement**

In `forge/gaia2/harbor.py`, change the import block (lines 28-35) to:

```python
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from forge.appworld.harbor import _difficulty
from forge.appworld.partition import Constraints, Topology, Visibility
from forge.gaia2.judge_parse import JUDGE_PARSE_VERSION
from forge.gaia2.runtime import (
    OBJECTIVE_ACTION_CONTRACT,
    OBJECTIVE_ACTION_CONTRACT_VERSION,
)
```

Insert immediately before `def write_task(`:

```python
def derive_token(scenario_id: str, label: str) -> str:
    """The verifier token for one cell, derived rather than drawn.

    It gates only the sidecar's /state endpoint and sits in the task
    directory in the clear, so randomness bought nothing except a diff on
    every re-render. Deriving it from the cell and the two versions that
    define what the task measures makes a re-render of an unchanged cell a
    no-op and a contract or parse change visible in the token itself.
    """
    seed = (f"{scenario_id}|{label}|{OBJECTIVE_ACTION_CONTRACT_VERSION}"
            f"|{JUDGE_PARSE_VERSION}")
    return hashlib.sha256(seed.encode()).hexdigest()[:32]


def runtime_digest() -> str:
    """Content digest of everything a task ships verbatim, in manifest order.

    Changes when and only when a shipped source changes; the drift test and
    the viewer read it against each task's provenance.json.
    """
    h = hashlib.sha256()
    for dest, src in VERBATIM_COPIES.items():
        h.update(dest.encode())
        h.update(b"\0")
        h.update(Path(src).read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def _put(path: Path, text: str) -> bool:
    """Write `text` to `path` only if the bytes differ. Returns True if it
    wrote. A re-render then produces a git diff of exactly what changed."""
    data = text.encode()
    if path.exists() and path.read_bytes() == data:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return True


def provenance(scenario_id: str, constraints: Constraints) -> dict:
    """What a task was rendered from: the cell, and the versions of the
    three things that decide what it measures."""
    return {
        "scenario_id": scenario_id,
        "config": constraints.label,
        "objective_action_contract": OBJECTIVE_ACTION_CONTRACT_VERSION,
        "judge_parse": JUDGE_PARSE_VERSION,
        "runtime_digest": runtime_digest(),
    }
```

Replace the body of `write_task` (keep its signature and docstring) with:

```python
    label = constraints.label
    task_dir = Path(out_dir) / f"gaia2-{label}-{scenario_id}"
    (task_dir / "environment").mkdir(parents=True, exist_ok=True)
    (task_dir / "tests").mkdir(parents=True, exist_ok=True)
    (task_dir / "solution").mkdir(parents=True, exist_ok=True)

    config = {
        "roster": list(constraints.roster),
        "topology": constraints.topology.value,
        "visibility": constraints.visibility.value,
        # Gaia2's bN is deliberately soft: the sidecar records an auxiliary
        # economy signal but never refuses delegation N+1.
        "delegation_target": constraints.delegation_budget,
    }

    _put(task_dir / "task.toml", _TASK_TOML.format(
        label=label, scenario_id=scenario_id,
        roster="+".join(constraints.roster),
        difficulty=_difficulty(constraints)))

    _put(task_dir / "instruction.md", render_instruction(constraints))

    env = task_dir / "environment"
    _put(env / "docker-compose.yaml", _COMPOSE.format(
        config_json=json.dumps(config), token=token))
    _put(env / "Dockerfile", _MAIN_DOCKERFILE)

    # The world itself. Byte-identical to the fetched scenario file, so a
    # reviewer can diff a shipped task against the dataset.
    _put(env / "scenario.json", Path(scenario_path).read_text())

    for dest, src in VERBATIM_COPIES.items():
        _put(task_dir / dest, Path(src).read_text())

    _put(task_dir / "tests" / "verifier_token.txt", token)
    _put(task_dir / "tests" / "test.sh",
         "#!/bin/bash\nmkdir -p /logs/verifier\npython3 /tests/verify.py\n")

    _put(task_dir / "solution" / "solve.sh", _SOLVE_NO_REFERENCE)

    _put(task_dir / "provenance.json",
         json.dumps(provenance(scenario_id, constraints), indent=1) + "\n")

    os.chmod(task_dir / "tests" / "test.sh", 0o755)
    os.chmod(task_dir / "solution" / "solve.sh", 0o755)
    os.chmod(env / "team", 0o755)
    return task_dir
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `$PY -m pytest forge/tests/test_gaia2_harbor.py -q -p no:cacheprovider`
Expected: all pass (the fixture-based tests now run because Step 1 linked the data).

- [ ] **Step 6: Lint and full suite**

Run: `$PY -m ruff check forge scripts && $PY -m pytest -q -p no:cacheprovider | tail -2`
Expected: ruff clean; suite green (the three committed tasks under `tasks/gaia2-*` still pass `test_committed_tasks_match_the_generator` because `VERBATIM_COPIES` did not change).

- [ ] **Step 7: Commit**

```bash
git add forge/gaia2/harbor.py forge/tests/test_gaia2_harbor.py
git commit -m "Render deterministically: derived token, write-if-changed, provenance with a runtime digest"
```

---

### Task 2: The grid in one place

**Files:**
- Create: `forge/gaia2/grid.py`
- Modify: `scripts/gaia2_campaign.py` (lines 27-37 imports and `GRID`; `eligible` lines 40-59; `scenario_paths` lines 60-74; job loop lines 105-135)
- Modify: `forge/gaia2/__init__.py` docstring (line 14: add a `grid.py` bullet)
- Modify: `forge/tests/test_gaia2_campaign.py` line 16
- Test: `forge/tests/test_gaia2_grid.py`

**Interfaces:**
- Consumes: `admit` from `forge.gaia2.mine`; `Ability`, `config_for` from `forge.abilities`; `Constraints`, `control_for` from `forge.appworld.partition`.
- Produces:
  ```python
  GRID: tuple  # (None, Ability.DISCOVERY, Ability.CONTEXT_TRANSFER, Ability.DELEGATION_ECONOMY)
  @dataclass(frozen=True)
  class Cell:
      scenario_id: str
      scenario_path: Path
      ability: Ability | None
      constraints: Constraints
      soft_judge: bool
      economy_target: int
      task_name: str  # property: f"gaia2-{constraints.label}-{scenario_id}"
  def eligible(span, scripted_only: bool) -> bool
  def scenario_paths(root: Path) -> dict[str, Path]
  def cells_for(scenario_path: Path, *, economy_target: int | None = None,
                economy_target_offset: int = 0) -> list[Cell]   # the four cells of one scenario; [] if not admitted
  def cells(root: Path, *, scripted_only: bool = False, economy_target: int | None = None,
            economy_target_offset: int = 0) -> list[Cell]
  ```

- [ ] **Step 1: Write the failing tests**

Create `forge/tests/test_gaia2_grid.py`:

```python
"""The campaign grid, defined once. The campaign, the render command and the
drift guard all read it from here, so they cannot disagree about which cells
exist."""

import json
from pathlib import Path
from types import SimpleNamespace

from forge.abilities import Ability
from forge.gaia2 import grid
from forge.gaia2.grid import GRID, Cell, cells, cells_for, eligible, scenario_paths


def span(usable=True, seamful=True, reply_conditioned=False, roster_blind=(),
         roster=("Cabs", "Calendar", "Messages"), delegation_target=6,
         scenario_id="scenario_a"):
    return SimpleNamespace(usable=usable, seamful=seamful,
                           reply_conditioned=reply_conditioned,
                           roster_blind=roster_blind, roster=roster,
                           delegation_target=delegation_target,
                           scenario_id=scenario_id)


def _root(tmp_path: Path, sids_mini=("scenario_a",), sids_adapt=("scenario_b",),
          fetched=("scenario_a", "scenario_b")) -> Path:
    (tmp_path / "sweep").mkdir()
    (tmp_path / "sweep" / "gaia2_cells.json").write_text(json.dumps(
        [{"scenario_id": s, "config": "open-docs-binf"} for s in sids_mini]))
    (tmp_path / "sweep" / "gaia2_cells_adaptability.json").write_text(json.dumps(
        [{"scenario_id": s, "config": "open-docs-binf"} for s in sids_adapt]))
    for split, sids in (("mini", sids_mini), ("adaptability", sids_adapt)):
        (tmp_path / "gaia2_data" / split).mkdir(parents=True)
        for s in sids:
            if s in fetched:
                (tmp_path / "gaia2_data" / split / f"{s}.json").write_text(
                    json.dumps({"scenario_id": s}))
    return tmp_path


def test_the_grid_is_the_control_and_the_three_abilities():
    assert GRID == (None, Ability.DISCOVERY, Ability.CONTEXT_TRANSFER,
                    Ability.DELEGATION_ECONOMY)


def test_eligible_keeps_the_campaign_s_rules():
    assert not eligible(span(usable=False), scripted_only=False)
    assert not eligible(span(seamful=False), scripted_only=True)
    assert eligible(span(reply_conditioned=True), scripted_only=False)
    assert not eligible(span(reply_conditioned=True), scripted_only=True)
    assert not eligible(span(roster_blind=(("Emails", "send_email", "x"),)),
                        scripted_only=False)


def test_scenario_paths_prefers_mini_and_skips_unfetched(tmp_path):
    root = _root(tmp_path, sids_mini=("scenario_a",),
                 sids_adapt=("scenario_a", "scenario_b", "scenario_c"),
                 fetched=("scenario_a", "scenario_b"))
    paths = scenario_paths(root)
    assert set(paths) == {"scenario_a", "scenario_b"}
    assert paths["scenario_a"].parent.name == "mini"
    assert paths["scenario_b"].parent.name == "adaptability"


def test_cells_for_yields_four_cells_with_the_scenario_s_target(tmp_path, monkeypatch):
    root = _root(tmp_path)
    monkeypatch.setattr(grid, "admit", lambda scenario: span(
        scenario_id=scenario["scenario_id"], delegation_target=5,
        reply_conditioned=True))
    out = cells_for(root / "gaia2_data" / "mini" / "scenario_a.json")
    assert [c.ability for c in out] == list(GRID)
    assert [c.constraints.label for c in out] == [
        "open-docs-binf", "star-names-binf", "star-docs-binf", "star-docs-b5"]
    assert all(c.scenario_id == "scenario_a" and c.soft_judge for c in out)
    assert all(c.economy_target == 5 for c in out)
    assert out[3].task_name == "gaia2-star-docs-b5-scenario_a"
    assert isinstance(out[0], Cell)


def test_cells_for_returns_nothing_for_an_inadmissible_scenario(tmp_path, monkeypatch):
    root = _root(tmp_path)
    monkeypatch.setattr(grid, "admit", lambda scenario: span(seamful=False))
    assert cells_for(root / "gaia2_data" / "mini" / "scenario_a.json") == []


def test_economy_target_override_and_offset(tmp_path, monkeypatch):
    root = _root(tmp_path)
    monkeypatch.setattr(grid, "admit", lambda scenario: span(delegation_target=6))
    p = root / "gaia2_data" / "mini" / "scenario_a.json"
    assert cells_for(p, economy_target=2)[3].constraints.label == "star-docs-b2"
    assert cells_for(p, economy_target_offset=-10)[3].constraints.label == "star-docs-b1"
    assert cells_for(p, economy_target_offset=1)[3].constraints.label == "star-docs-b7"


def test_cells_walks_every_fetched_scenario_in_id_order(tmp_path, monkeypatch):
    root = _root(tmp_path)
    monkeypatch.setattr(grid, "admit", lambda scenario: span(
        scenario_id=scenario["scenario_id"],
        reply_conditioned=scenario["scenario_id"] == "scenario_b"))
    out = cells(root)
    assert [c.scenario_id for c in out] == ["scenario_a"] * 4 + ["scenario_b"] * 4
    assert [c.soft_judge for c in out] == [False] * 4 + [True] * 4
    assert [c.scenario_id for c in cells(root, scripted_only=True)] == ["scenario_a"] * 4
```

The label expectations (`star-names-binf` for discovery, `star-docs-binf` for context transfer, `star-docs-b{N}` for economy) are what `forge.abilities.config_for` produces today; the test pins them.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `$PY -m pytest forge/tests/test_gaia2_grid.py -q -p no:cacheprovider`
Expected: `ModuleNotFoundError: No module named 'forge.gaia2.grid'`.

- [ ] **Step 3: Create `forge/gaia2/grid.py`**

Move `GRID`, `eligible` and `scenario_paths` out of `scripts/gaia2_campaign.py` byte-for-byte (docstrings included), giving `scenario_paths` a `root` parameter in place of the module-level `ROOT`, and add `Cell`, `cells_for`, `cells`:

```python
"""The Gaia2 campaign grid, defined once.

The grid is every admitted seamful scenario with a fetched file (mini first,
then adaptability) crossed with the OPEN control and the three one-knob
ability cells. The campaign runs it, `forge.gaia2.cli render --all` renders
it, and `forge/tests/test_gaia2_tasks_current.py` checks the rendered tasks
against it -- all through this module, so none of the three can hold a
different opinion about which cells exist.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from forge.abilities import Ability, config_for
from forge.appworld.partition import Constraints, control_for
from forge.gaia2.mine import admit

#: None is the OPEN control; the rest are the one-knob ability cells.
GRID = (None, Ability.DISCOVERY, Ability.CONTEXT_TRANSFER,
        Ability.DELEGATION_ECONOMY)

#: Where the grid's scenarios are listed, and the split each list came from.
CELL_FILES = (("sweep/gaia2_cells.json", "mini"),
              ("sweep/gaia2_cells_adaptability.json", "adaptability"))


@dataclass(frozen=True)
class Cell:
    """One (scenario, configuration) pair: what one campaign episode runs and
    what one Harbor task ships."""
    scenario_id: str
    scenario_path: Path
    ability: Ability | None
    constraints: Constraints
    soft_judge: bool
    economy_target: int

    @property
    def task_name(self) -> str:
        return f"gaia2-{self.constraints.label}-{self.scenario_id}"


def eligible(span, scripted_only: bool) -> bool:
    """Admission, plus the optional judge-uniform restriction.

    `--scripted-only` exists because the grader is welded to the scenario:
    reply-conditioned scenarios can only run under the soft judge, and in the
    v3 campaign that judge's column was all zeros -- so every cross-arm
    comparison rode on the 5 of 37 scenarios the deterministic verifier
    grades. A seed spent under this flag buys 20 cells that can actually
    move, instead of 148 of which 128 are structurally pinned to zero.
    """
    if not (span.usable and span.seamful):
        return False
    if span.roster_blind:
        # The partition provably omits a fact the gold writes consume (see
        # mine.BlindFact): every seat is locked out of it, so every episode
        # is a guaranteed failure. v4 bought four of these on one scenario.
        return False
    return not (scripted_only and span.reply_conditioned)


def scenario_paths(root: Path) -> dict[str, Path]:
    """Every unique seamful scenario with a fetched file, mini first."""
    seen: dict[str, Path] = {}
    for cells_file, split in CELL_FILES:
        for cell in json.loads((root / cells_file).read_text()):
            sid = cell["scenario_id"]
            if sid in seen:
                continue
            path = root / "gaia2_data" / split / f"{sid}.json"
            if path.exists():
                seen[sid] = path
    return seen


def _target(span, economy_target: int | None, economy_target_offset: int) -> int:
    if economy_target is not None:
        return economy_target
    return max(1, span.delegation_target + economy_target_offset)


def cells_for(scenario_path: Path, *, economy_target: int | None = None,
              economy_target_offset: int = 0,
              scripted_only: bool = False) -> list[Cell]:
    """The four cells of one scenario, or none if it is not admitted."""
    scenario_path = Path(scenario_path)
    span = admit(json.loads(scenario_path.read_text()))
    if not eligible(span, scripted_only):
        return []
    target = _target(span, economy_target, economy_target_offset)
    out = []
    for ability in GRID:
        constraints = (control_for(span.roster) if ability is None
                       else config_for(ability, span.roster, budget_target=target))
        out.append(Cell(span.scenario_id, scenario_path, ability, constraints,
                        span.reply_conditioned, target))
    return out


def cells(root: Path, *, scripted_only: bool = False,
          economy_target: int | None = None,
          economy_target_offset: int = 0) -> list[Cell]:
    """The whole grid, scenarios in id order, four cells each."""
    out: list[Cell] = []
    for _sid, path in sorted(scenario_paths(root).items()):
        out.extend(cells_for(path, economy_target=economy_target,
                             economy_target_offset=economy_target_offset,
                             scripted_only=scripted_only))
    return out
```

Note `span.scenario_id` is what `admit` returns today (`cmd_render` in `cli.py` prints it), so `Cell.scenario_id` comes from the span, not the filename.

- [ ] **Step 4: Point the campaign at the grid**

In `scripts/gaia2_campaign.py`:

Replace lines 27-37 (the imports through `GRID`) with:

```python
from forge.abilities import Ability
from forge.gaia2.grid import cells
from scripts.embed_logs import try_refresh

ROOT = Path(__file__).resolve().parents[1]
GAIA2_PY = ROOT / ".venv-gaia2" / "bin" / "python"
```

Delete `eligible` (lines 40-59) and `scenario_paths` (lines 60-74) from the script; `json` stays imported only if still used (it is not; remove `import json` too and let ruff confirm).

Replace the job-building loop (from `jobs = []` through `jobs.append(...)`) with:

```python
    grid = cells(ROOT, scripted_only=args.scripted_only,
                 economy_target=args.economy_target,
                 economy_target_offset=args.economy_target_offset)
    jobs = []
    skipped = 0
    for cell in grid:
        existing = list((ROOT / args.out).glob(
            f"gaia2__{cell.scenario_id}__{cell.constraints.label}*__{args.label}__*.json"))
        if existing:
            skipped += 1
            continue
        cmd = [str(GAIA2_PY), "-m", "scripts.gaia2_cell_run",
               "--scenario", str(cell.scenario_path),
               "--ability", "control" if cell.ability is None else cell.ability.value,
               "--label", args.label, "--out", args.out]
        if cell.ability is Ability.DELEGATION_ECONOMY:
            cmd += ["--economy-target", str(cell.economy_target)]
        if cell.soft_judge:
            cmd += ["--judge-model", args.judge_model]
        jobs.append((cell.scenario_id, cell.constraints.label, cell.soft_judge, cmd))
```

Everything after (`print(f"{len(jobs)} cells to run ...`, dry-run, `run_one`, the pool, `try_refresh`) stays as it is.

In `forge/tests/test_gaia2_campaign.py` line 16, change `from scripts.gaia2_campaign import eligible` to `from forge.gaia2.grid import eligible`.

In `forge/gaia2/__init__.py`, add after the `are_world.py` bullet:

```
  * `grid.py` -- the campaign grid (scenarios x configurations), defined once
    for the campaign, the render command and the drift guard.
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `$PY -m pytest forge/tests/test_gaia2_grid.py forge/tests/test_gaia2_campaign.py -q -p no:cacheprovider`
Expected: all pass.

- [ ] **Step 6: Confirm the move was a move**

```bash
SCRATCH=$(mktemp -d)
git show HEAD:scripts/gaia2_campaign.py | sed -n '40,59p' > "$SCRATCH/eligible_before.txt"
sed -n '/^def eligible/,/^    return not/p' forge/gaia2/grid.py > "$SCRATCH/eligible_after.txt"
diff "$SCRATCH/eligible_before.txt" "$SCRATCH/eligible_after.txt" && echo "eligible moved verbatim"
```

Expected: `eligible moved verbatim`. Then a dry run over the real grid must still list 132 cells:

```bash
$PY -m scripts.gaia2_campaign --label plancheck --dry-run | head -1
```

Expected: `132 cells to run (0 already done, resumed past)`. (This imports `forge.gaia2.mine` and `forge.abilities` only; no `are.*`.)

- [ ] **Step 7: Lint and full suite, then commit**

Run: `$PY -m ruff check forge scripts && $PY -m pytest -q -p no:cacheprovider | tail -2`

```bash
git add forge/gaia2/grid.py forge/gaia2/__init__.py scripts/gaia2_campaign.py forge/tests/test_gaia2_grid.py forge/tests/test_gaia2_campaign.py
git commit -m "Define the campaign grid once, in forge/gaia2/grid.py"
```

---

### Task 3: `render --all`, the manifest, and four cells per scenario

**Files:**
- Modify: `forge/gaia2/harbor.py` (append after `write_task`)
- Modify: `forge/gaia2/cli.py` (whole file)
- Test: `forge/tests/test_gaia2_cli.py` (new); `forge/tests/test_gaia2_harbor.py` (append)

**Interfaces:**
- Consumes: `Cell`, `cells`, `cells_for` from Task 2; `write_task`, `derive_token`, `_put` from Task 1.
- Produces:
  ```python
  def write_manifest(grid: list[Cell], out_dir: Path) -> Path      # tasks/MANIFEST.json
  def render_grid(grid: list[Cell], out_dir: Path) -> list[Path]   # renders every cell, then the manifest
  ```
  CLI: `python -m forge.gaia2.cli render --all [--out tasks] [--scripted-only] [--economy-target N | --economy-target-offset K]` and `python -m forge.gaia2.cli render --scenario PATH [--out tasks] [--economy-target N]`.

- [ ] **Step 1: Write the failing tests**

Append to `forge/tests/test_gaia2_harbor.py`:

```python
# -- the grid as rendered -----------------------------------------------------

from forge.gaia2.grid import Cell  # noqa: E402
from forge.gaia2.harbor import render_grid, write_manifest  # noqa: E402


def _cell(tmp_path, sid, constraints, soft):
    p = tmp_path / f"{sid}.json"
    p.write_text(json.dumps({"scenario_id": sid}))
    return Cell(sid, p, None, constraints, soft, 4)


def test_the_manifest_lists_every_cell_sorted_by_name(tmp_path):
    names = Constraints(roster=("Cabs", "Calendar"), topology=Topology.STAR,
                        visibility=Visibility.NAMES)
    grid = [_cell(tmp_path, "scenario_b", C, True), _cell(tmp_path, "scenario_a", names, False)]
    p = write_manifest(grid, tmp_path / "out")
    assert p == tmp_path / "out" / "MANIFEST.json"
    rows = json.loads(p.read_text())
    assert rows == [
        {"name": "gaia2-star-docs-binf-scenario_b", "scenario_id": "scenario_b",
         "config": "star-docs-binf", "soft_judge": True},
        {"name": "gaia2-star-names-binf-scenario_a", "scenario_id": "scenario_a",
         "config": "star-names-binf", "soft_judge": False},
    ]
    assert p.read_text().endswith("\n")


def test_render_grid_renders_each_cell_with_its_derived_token_and_the_manifest(tmp_path):
    grid = [_cell(tmp_path, "scenario_a", C, True)]
    dirs = render_grid(grid, tmp_path / "out")
    assert dirs == [tmp_path / "out" / "gaia2-star-docs-binf-scenario_a"]
    token = (dirs[0] / "tests" / "verifier_token.txt").read_text()
    assert token == derive_token("scenario_a", "star-docs-binf")
    assert (tmp_path / "out" / "MANIFEST.json").exists()
```

Create `forge/tests/test_gaia2_cli.py`:

```python
"""The render command: one scenario's four cells, or the whole grid."""

import json
from types import SimpleNamespace

import pytest

from forge.gaia2 import cli, grid
from forge.gaia2.harbor import derive_token


def _span(scenario, target=3):
    return SimpleNamespace(usable=True, seamful=True, reply_conditioned=False,
                           roster_blind=(), roster=("Cabs", "Calendar", "Messages"),
                           delegation_target=target,
                           scenario_id=scenario["scenario_id"])


@pytest.fixture
def world(tmp_path, monkeypatch):
    (tmp_path / "sweep").mkdir()
    (tmp_path / "sweep" / "gaia2_cells.json").write_text(json.dumps(
        [{"scenario_id": "scenario_a"}]))
    (tmp_path / "sweep" / "gaia2_cells_adaptability.json").write_text("[]")
    (tmp_path / "gaia2_data" / "mini").mkdir(parents=True)
    (tmp_path / "gaia2_data" / "mini" / "scenario_a.json").write_text(
        json.dumps({"scenario_id": "scenario_a"}))
    monkeypatch.setattr(grid, "admit", _span)
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    return tmp_path


def test_render_scenario_writes_the_four_grid_cells_with_derived_tokens(world, capsys):
    cli.main(["render", "--scenario", str(world / "gaia2_data" / "mini" / "scenario_a.json"),
              "--out", str(world / "tasks")])
    names = sorted(p.name for p in (world / "tasks").glob("gaia2-*"))
    assert names == ["gaia2-open-docs-binf-scenario_a", "gaia2-star-docs-b3-scenario_a",
                     "gaia2-star-docs-binf-scenario_a", "gaia2-star-names-binf-scenario_a"]
    tok = (world / "tasks" / "gaia2-star-docs-b3-scenario_a" / "tests" / "verifier_token.txt").read_text()
    assert tok == derive_token("scenario_a", "star-docs-b3")
    assert not (world / "tasks" / "MANIFEST.json").exists(), "one scenario is not the grid"
    out = capsys.readouterr().out
    assert "gaia2-open-docs-binf-scenario_a" in out


def test_render_all_writes_the_grid_and_the_manifest(world):
    cli.main(["render", "--all", "--out", str(world / "tasks")])
    rows = json.loads((world / "tasks" / "MANIFEST.json").read_text())
    assert [r["name"] for r in rows] == [
        "gaia2-open-docs-binf-scenario_a", "gaia2-star-docs-b3-scenario_a",
        "gaia2-star-docs-binf-scenario_a", "gaia2-star-names-binf-scenario_a"]
    assert all((world / "tasks" / r["name"] / "provenance.json").exists() for r in rows)


def test_render_all_honours_the_economy_target(world):
    cli.main(["render", "--all", "--out", str(world / "tasks"), "--economy-target", "7"])
    assert (world / "tasks" / "gaia2-star-docs-b7-scenario_a").exists()


def test_render_refuses_a_scenario_that_is_not_admitted(world, monkeypatch):
    monkeypatch.setattr(grid, "admit", lambda s: SimpleNamespace(
        usable=False, seamful=False, reply_conditioned=False, roster_blind=(),
        roster=(), delegation_target=1, scenario_id="scenario_a"))
    with pytest.raises(SystemExit):
        cli.main(["render", "--scenario", str(world / "gaia2_data" / "mini" / "scenario_a.json"),
                  "--out", str(world / "tasks")])


def test_scenario_and_all_are_exclusive(world):
    with pytest.raises(SystemExit):
        cli.main(["render", "--all", "--scenario", "x.json"])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `$PY -m pytest forge/tests/test_gaia2_cli.py forge/tests/test_gaia2_harbor.py -q -p no:cacheprovider`
Expected: ImportError on `render_grid`, `write_manifest`; the cli tests fail on `--all` being unknown and `ROOT` missing.

- [ ] **Step 3: Implement in `forge/gaia2/harbor.py`**

Add `from forge.gaia2.grid import Cell` to the import block, and append after `write_task`:

```python
def write_manifest(grid: list[Cell], out_dir: str | Path) -> Path:
    """`tasks/MANIFEST.json`: the grid as rendered, readable on a clone that
    has no gaia2_data. One row per cell, sorted by task name."""
    rows = sorted(
        ({"name": c.task_name, "scenario_id": c.scenario_id,
          "config": c.constraints.label, "soft_judge": c.soft_judge}
         for c in grid),
        key=lambda r: r["name"])
    path = Path(out_dir) / "MANIFEST.json"
    _put(path, json.dumps(rows, indent=1) + "\n")
    return path


def render_grid(grid: list[Cell], out_dir: str | Path) -> list[Path]:
    """Render every cell with its derived token, then the manifest."""
    dirs = [write_task(c.scenario_path, c.scenario_id, c.constraints, out_dir,
                       token=derive_token(c.scenario_id, c.constraints.label))
            for c in grid]
    write_manifest(grid, out_dir)
    return dirs
```

- [ ] **Step 4: Rewrite `forge/gaia2/cli.py`**

```python
"""Render Gaia2 scenarios into Harbor tasks.

    python -m forge.gaia2.cli render --all                      # the whole grid + tasks/MANIFEST.json
    python -m forge.gaia2.cli render --scenario gaia2_data/mini/scenario_universe_30_68r6vs.json

A task is one cell of the campaign grid (`forge/gaia2/grid.py`): the OPEN
control and the three one-knob ability cells of an admitted scenario. The
campaign renders the same cells before it runs them; this command renders
without running. Tokens are derived (`harbor.derive_token`), files are
rewritten only when their bytes change, and every task carries a
`provenance.json` -- so a re-render is a diff of exactly what changed, and
`forge/tests/test_gaia2_tasks_current.py` can tell a stale task from a
current one.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from forge.gaia2.grid import cells, cells_for
from forge.gaia2.harbor import derive_token, render_grid, write_task

ROOT = Path(__file__).resolve().parents[2]


def cmd_render(args: argparse.Namespace) -> None:
    if args.economy_target is not None and args.economy_target < 1:
        raise SystemExit("--economy-target must be positive")
    if args.all:
        grid = cells(ROOT, scripted_only=args.scripted_only,
                     economy_target=args.economy_target,
                     economy_target_offset=args.economy_target_offset)
        dirs = render_grid(grid, args.out)
        print(f"rendered {len(dirs)} tasks and {Path(args.out) / 'MANIFEST.json'}")
        return
    scenario_path = Path(args.scenario)
    grid = cells_for(scenario_path, economy_target=args.economy_target,
                     economy_target_offset=args.economy_target_offset)
    if not grid:
        raise SystemExit(
            f"{scenario_path.name}: not admitted (usable and seamful, and not "
            "roster-blind) -- only admitted scenarios render; see "
            "sweep/gaia2_*_admission.json")
    print(f"{grid[0].scenario_id}: roster {grid[0].constraints.roster}")
    for c in grid:
        d = write_task(c.scenario_path, c.scenario_id, c.constraints, args.out,
                       token=derive_token(c.scenario_id, c.constraints.label))
        print(f"  {d.name}   ({'control' if c.ability is None else c.ability.value})")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="forge.gaia2.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)

    render = sub.add_parser("render", help="render one scenario's four cells, "
                            "or the whole grid with --all")
    which = render.add_mutually_exclusive_group(required=True)
    which.add_argument("--scenario", help="path to a fetched scenario JSON")
    which.add_argument("--all", action="store_true",
                       help="every cell of the campaign grid, plus MANIFEST.json")
    render.add_argument("--out", type=Path, default=Path("tasks"))
    render.add_argument("--scripted-only", action="store_true",
                        help="with --all: only scenarios the scripted judge grades")
    target = render.add_mutually_exclusive_group()
    target.add_argument("--economy-target", type=int, default=None,
                        help="one explicit soft bN target for every economy cell")
    target.add_argument("--economy-target-offset", type=int, default=0,
                        help="add this amount to each task-derived economy heuristic")
    render.set_defaults(fn=cmd_render)

    args = parser.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main(sys.argv[1:])
```

The blind-roster message that `cmd_render` used to print in full is now `eligible`'s decision inside `cells_for`; the campaign never printed it either, and `scripts/gaia2_cell_run.py` still refuses a blind scenario with the itemised message before spending.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `$PY -m pytest forge/tests/test_gaia2_cli.py forge/tests/test_gaia2_harbor.py -q -p no:cacheprovider`
Expected: all pass.

- [ ] **Step 6: Lint, full suite, commit**

Run: `$PY -m ruff check forge scripts && $PY -m pytest -q -p no:cacheprovider | tail -2`

```bash
git add forge/gaia2/harbor.py forge/gaia2/cli.py forge/tests/test_gaia2_cli.py forge/tests/test_gaia2_harbor.py
git commit -m "render --all: the grid and its manifest; render --scenario: four cells, derived tokens"
```

---

### Task 4: The campaign renders what it measures

**Files:**
- Modify: `scripts/gaia2_campaign.py` (after the dry-run return, before `run_one`)
- Test: `forge/tests/test_gaia2_campaign.py` (append)

**Interfaces:**
- Consumes: `render_grid` from Task 3; the `grid` list built in Task 2's loop.

- [ ] **Step 1: Write the failing test**

Append to `forge/tests/test_gaia2_campaign.py`:

```python
# -- the campaign renders every cell before it runs any -----------------------


def test_the_campaign_renders_the_grid_after_the_dry_run_return_and_before_any_job():
    src = (_SCRIPTS / "gaia2_campaign.py").read_text()
    assert "from forge.gaia2.harbor import render_grid" in src
    call = src.index("render_grid(grid, ROOT / \"tasks\")")
    dry = src.index("if args.dry_run:")
    assert dry < call, "--dry-run must return before anything is rendered"
    assert call < src.index("def run_one"), "render before the pool is built"
    assert "--no-render" not in src, "rendering is not optional"


def test_the_campaign_reports_what_it_rendered():
    src = (_SCRIPTS / "gaia2_campaign.py").read_text()
    assert 'print(f"rendered {len(rendered)} tasks under tasks/")' in src
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `$PY -m pytest forge/tests/test_gaia2_campaign.py -q -p no:cacheprovider`
Expected: the two new tests fail on the missing import and call.

- [ ] **Step 3: Implement**

In `scripts/gaia2_campaign.py`, add to the imports:

```python
from forge.gaia2.harbor import render_grid
```

Immediately after the dry-run block (which ends with `return`) and before `def run_one(job):`, insert:

```python
    # The shipped form follows the measured form: every cell in this grid,
    # done or not, is rendered from the same scenario and constraints it
    # runs under, so tasks/ cannot lag what the campaign measured.
    rendered = render_grid(grid, ROOT / "tasks")
    print(f"rendered {len(rendered)} tasks under tasks/")
```

Update the module docstring's last paragraph to end:

```
skipped -- kill the campaign and relaunch it freely. Before running, the
campaign renders every cell of the grid as a Harbor task under `tasks/`
(`forge/gaia2/harbor.render_grid`), so the shipped tasks are always the
cells that were measured. `--dry-run` prints the work list, renders nothing
and prices nothing.
```

- [ ] **Step 4: Run the tests, lint, full suite**

Run: `$PY -m pytest forge/tests/test_gaia2_campaign.py -q -p no:cacheprovider && $PY -m ruff check forge scripts && $PY -m pytest -q -p no:cacheprovider | tail -2`
Expected: green.

- [ ] **Step 5: Commit**

```bash
git add scripts/gaia2_campaign.py forge/tests/test_gaia2_campaign.py
git commit -m "The campaign renders every cell of its grid before it runs one"
```

---

### Task 5: The drift guard, and the grid rendered for real

**Files:**
- Create: `forge/tests/test_gaia2_tasks_current.py`
- Create/replace: `tasks/gaia2-*` (132 directories), `tasks/MANIFEST.json`

**Interfaces:**
- Consumes: `VERBATIM_COPIES`, `derive_token`, `runtime_digest` from `forge.gaia2.harbor`; `OBJECTIVE_ACTION_CONTRACT`, `OBJECTIVE_ACTION_CONTRACT_VERSION` from `forge.gaia2.runtime`; `JUDGE_PARSE_VERSION` from `forge.gaia2.judge_parse`.

- [ ] **Step 1: Write the drift guard**

Create `forge/tests/test_gaia2_tasks_current.py`:

```python
"""The rendered grid under tasks/ must be the grid the runtime would render
now. Runnable on a clone without gaia2_data: everything but the world
byte-identity check reads only tracked files.

Fix for every failure here: `python -m forge.gaia2.cli render --all`."""

import json
import re
from pathlib import Path

import pytest

from forge.gaia2.harbor import VERBATIM_COPIES, derive_token, runtime_digest
from forge.gaia2.judge_parse import JUDGE_PARSE_VERSION
from forge.gaia2.runtime import (
    OBJECTIVE_ACTION_CONTRACT,
    OBJECTIVE_ACTION_CONTRACT_VERSION,
)

REPO = Path(__file__).resolve().parents[2]
TASKS = REPO / "tasks"
MANIFEST = TASKS / "MANIFEST.json"
FIX = "re-render with `python -m forge.gaia2.cli render --all`"

_rows = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else []
_ids = [r["name"] for r in _rows]


def test_the_manifest_exists_and_names_the_grid():
    assert MANIFEST.exists(), f"tasks/MANIFEST.json is missing -- {FIX}"
    assert _rows == sorted(_rows, key=lambda r: r["name"])
    assert all(set(r) == {"name", "scenario_id", "config", "soft_judge"} for r in _rows)
    assert len(_rows) >= 100, "the grid is 132 cells; a manifest this short is a partial render"


def test_every_manifest_entry_is_a_task_and_every_gaia2_task_is_an_entry():
    on_disk = {p.name for p in TASKS.glob("gaia2-*") if p.is_dir()}
    assert on_disk == set(_ids), (
        f"tasks/ and MANIFEST.json disagree: only on disk {sorted(on_disk - set(_ids))}, "
        f"only in manifest {sorted(set(_ids) - on_disk)} -- {FIX}")


@pytest.mark.parametrize("name", _ids)
def test_each_task_ships_the_current_runtime(name):
    task = TASKS / name
    for dest, src in VERBATIM_COPIES.items():
        assert (task / dest).read_bytes() == Path(src).read_bytes(), (
            f"{name} ships a stale {dest} -- {FIX}")


@pytest.mark.parametrize("row", _rows, ids=_ids)
def test_each_task_s_provenance_is_current(row):
    task = TASKS / row["name"]
    prov = json.loads((task / "provenance.json").read_text())
    assert prov == {
        "scenario_id": row["scenario_id"],
        "config": row["config"],
        "objective_action_contract": OBJECTIVE_ACTION_CONTRACT_VERSION,
        "judge_parse": JUDGE_PARSE_VERSION,
        "runtime_digest": runtime_digest(),
    }, f"{row['name']} was rendered from an older runtime, contract or parse -- {FIX}"


@pytest.mark.parametrize("row", _rows, ids=_ids)
def test_each_task_s_instruction_carries_the_current_contract(row):
    text = (TASKS / row["name"] / "instruction.md").read_text()
    assert OBJECTIVE_ACTION_CONTRACT in text and OBJECTIVE_ACTION_CONTRACT_VERSION in text, (
        f"{row['name']} briefs the Main under an older contract -- {FIX}")


@pytest.mark.parametrize("row", _rows, ids=_ids)
def test_each_task_s_token_is_the_derived_one(row):
    token = (TASKS / row["name"] / "tests" / "verifier_token.txt").read_text()
    assert token == derive_token(row["scenario_id"], row["config"]), (
        f"{row['name']} carries a token that is not derived from its cell -- {FIX}")


@pytest.mark.parametrize("row", _rows, ids=_ids)
def test_each_task_s_world_is_the_dataset_file(row):
    candidates = list((REPO / "gaia2_data").glob(f"*/{row['scenario_id']}.json"))
    if not candidates:
        pytest.skip("gaia2_data is not fetched (gitignored)")
    shipped = (TASKS / row["name"] / "environment" / "scenario.json").read_bytes()
    assert any(shipped == p.read_bytes() for p in candidates), (
        f"{row['name']} ships a world that differs from the dataset file -- {FIX}")


def test_the_fix_named_here_is_a_command_that_exists():
    src = (REPO / "forge" / "gaia2" / "cli.py").read_text()
    assert re.search(r'"--all"', src), "the render command lost --all"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `$PY -m pytest forge/tests/test_gaia2_tasks_current.py -q -p no:cacheprovider`
Expected: `test_the_manifest_exists_and_names_the_grid` fails (no manifest); the parametrized tests are simply absent.

- [ ] **Step 3: Render the grid**

```bash
$PY -m forge.gaia2.cli render --all
ls -d tasks/gaia2-* | wc -l
du -sh tasks
```

Expected: `rendered 132 tasks and tasks/MANIFEST.json`; the count is `132`; roughly 370 MB. The three old `gaia2-*-scenario_universe_30_68r6vs` directories are overwritten in place (same names), so no stale directory survives.

- [ ] **Step 4: Verify**

Run: `$PY -m pytest forge/tests/test_gaia2_tasks_current.py forge/tests/test_gaia2_harbor.py -q -p no:cacheprovider | tail -2`
Expected: green, including the existing `test_committed_tasks_*` tests now parametrized over 132 tasks.

Then prove idempotence on the real grid:

```bash
$PY -m forge.gaia2.cli render --all && git status --short tasks | wc -l
```

Expected: the second render changes nothing beyond what the first already staged: the count printed is the same before and after (compare with `git status --short tasks | wc -l` taken before the second render).

- [ ] **Step 5: Full suite and commit**

Run: `$PY -m ruff check forge scripts && $PY -m pytest -q -p no:cacheprovider | tail -2`

```bash
git add forge/tests/test_gaia2_tasks_current.py tasks/MANIFEST.json tasks/gaia2-*
git commit -q -m "Render the whole Gaia2 grid: 132 tasks, a manifest, and a drift guard that fails on a stale task"
git show --stat HEAD | tail -1
```

Expected: the stat line reports on the order of 2,000 files changed.

---

### Task 6: The index reads provenance and links campaigns

**Files:**
- Modify: `scripts/embed_logs.py` (`task_record` lines 165-204; `snapshot` lines 252-302; imports)
- Test: `forge/tests/test_embed_logs.py` (fixture at lines 131-161; append tests)

**Interfaces:**
- Consumes: `runtime_digest` from `forge.gaia2.harbor`.
- Produces:
  ```python
  def link_trajectories(index: list[dict], tasks: list[dict]) -> dict[str, list[dict]]
      # task name -> [{"label", "episodes", "passes", "judge_parse"}, ...], newest label first
  def task_record(task_dir, root, runs, campaigns=None, current_digest=None) -> dict
      # adds "judge_parse", "runtime_digest", "current" (True/False/None), "campaigns"
  ```

- [ ] **Step 1: Extend the fixture and write the failing tests**

In `forge/tests/test_embed_logs.py`, the `episode(...)` helper currently begins:

```python
def episode(label, started, *, success=False, stopped=False, events=None,
            judge="gpt-5.6-sol", parse=None):
    d = {
        "kind": "gaia2-episode", "scenario_id": "scenario_universe_21_x",
        "config": "star-docs-binf", "ability": "context-transfer",
```

Change those lines to (defaults unchanged, so every existing assertion holds):

```python
def episode(label, started, *, success=False, stopped=False, events=None,
            judge="gpt-5.6-sol", parse=None,
            scenario_id="scenario_universe_21_x", config="star-docs-binf"):
    d = {
        "kind": "gaia2-episode", "scenario_id": scenario_id,
        "config": config, "ability": "context-transfer",
```

In the `tree` fixture, after the Gaia2 task's `scenario.json` line, add:

```python
    (tmp_path / "tasks" / "gaia2-star-docs-b4-scenario_universe_30_x" / "provenance.json").write_text(json.dumps({
        "scenario_id": "scenario_universe_30_x", "config": "star-docs-b4",
        "objective_action_contract": "objective-actions-v3",
        "judge_parse": "case-insensitive-v1", "runtime_digest": "abc123"}))
```

and change the two v6 rollout lines so they belong to that task (the `full` and probe rollouts keep the helper's defaults, which name a different scenario):

```python
    (roll / "a__v6__1.json").write_text(json.dumps(episode(
        "v6", "2026-08-30 17:00:00", stopped=True,
        scenario_id="scenario_universe_30_x", config="star-docs-b4")))
    (roll / "b__v6__2.json").write_text(json.dumps(episode(
        "v6", "2026-08-30 18:00:00", success=True, parse="case-insensitive-v1",
        scenario_id="scenario_universe_30_x", config="star-docs-b4")))
```

Append tests:

```python
# -- provenance and campaign links --------------------------------------------

from scripts.embed_logs import link_trajectories  # noqa: E402


def test_a_task_record_reads_provenance_and_judges_currency(tree):
    d = tree / "tasks" / "gaia2-star-docs-b4-scenario_universe_30_x"
    r = task_record(d, tree, [], current_digest="abc123")
    assert (r["judge_parse"], r["runtime_digest"], r["current"]) == ("case-insensitive-v1", "abc123", True)
    r = task_record(d, tree, [], current_digest="zzz")
    assert r["current"] is False
    a = task_record(tree / "tasks" / "appworld-star-docs-binf-2a163ab_1", tree, [], current_digest="abc123")
    assert (a["judge_parse"], a["runtime_digest"], a["current"]) == (None, None, None)


def test_trajectories_link_by_scenario_and_config_grouped_by_campaign(tree):
    snap = snapshot(root=tree)
    gaia = next(t for t in snap["tasks"] if t["substrate"] == "gaia2")
    assert gaia["campaigns"] == [
        {"label": "v6", "episodes": 2, "passes": 1, "judge_parse": "case-insensitive-v1"},
    ]
    app = next(t for t in snap["tasks"] if t["substrate"] == "appworld")
    assert app["campaigns"] == []


def test_link_trajectories_puts_the_newest_campaign_first_and_ignores_probes():
    index = [
        {"scenario_id": "s", "config": "c", "label": "old", "started_at": "2026-01-01 00:00:00",
         "judge_parse": None, "verdict": {"success": True}},
        {"scenario_id": "s", "config": "c", "label": "new", "started_at": "2026-02-01 00:00:00",
         "judge_parse": "case-insensitive-v1", "verdict": {"success": False}},
        {"scenario_id": "s", "config": "c", "label": None, "started_at": "2026-03-01 00:00:00",
         "judge_parse": None, "verdict": {"success": True}},
        {"scenario_id": "s", "config": "other", "label": "new", "started_at": "2026-02-02 00:00:00",
         "judge_parse": None, "verdict": {"success": True}},
    ]
    tasks = [{"name": "gaia2-c-s", "substrate": "gaia2", "config": "c", "target": "s"},
             {"name": "appworld-c-t", "substrate": "appworld", "config": "c", "target": "t"}]
    links = link_trajectories(index, tasks)
    assert links == {
        "gaia2-c-s": [
            {"label": "new", "episodes": 1, "passes": 0, "judge_parse": "case-insensitive-v1"},
            {"label": "old", "episodes": 1, "passes": 1, "judge_parse": None},
        ],
        "appworld-c-t": [],
    }
```

Also update `test_the_snapshot_indexes_every_episode_lists_every_task_and_embeds_one_label`: its assertions still hold (labels, order, tasks, runs, files); no change needed unless the `episode` helper change altered `started_at` ordering, which it does not.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `$PY -m pytest forge/tests/test_embed_logs.py -q -p no:cacheprovider`
Expected: ImportError on `link_trajectories`; `task_record` rejects `current_digest`.

- [ ] **Step 3: Implement**

In `scripts/embed_logs.py`, add the import (keep the block alphabetised for ruff's `I` rule):

```python
from forge.gaia2.harbor import runtime_digest
```

Change `task_record`'s signature to

```python
def task_record(task_dir: Path, root: Path, runs: list[dict],
                campaigns: list[dict] | None = None,
                current_digest: str | None = None) -> dict:
```

and, before its `return`, read provenance:

```python
    prov_path = task_dir / "provenance.json"
    prov: dict = {}
    if prov_path.exists():
        try:
            prov = json.loads(prov_path.read_text())
        except json.JSONDecodeError:
            prov = {}
    digest = prov.get("runtime_digest")
    current = None if not prov else (digest == current_digest)
```

and add to the returned dict, after `"runs": runs,`:

```python
        "judge_parse": prov.get("judge_parse"),
        "runtime_digest": digest,
        "current": current,
        "campaigns": campaigns or [],
```

Add after `link_runs`:

```python
def link_trajectories(index: list[dict], tasks: list[dict]) -> dict[str, list[dict]]:
    """Which campaign episodes belong to which Gaia2 task: same scenario, same
    configuration. Grouped by campaign label, newest label first (by its
    latest start); unlabelled probes are not campaigns and are left out."""
    links: dict[str, list[dict]] = {t["name"]: [] for t in tasks}
    for t in tasks:
        if t.get("substrate") != "gaia2":
            continue
        groups: dict[str, dict] = {}
        for r in index:
            if r.get("scenario_id") != t.get("target") or r.get("config") != t.get("config"):
                continue
            label = r.get("label")
            if label is None:
                continue
            g = groups.setdefault(label, {"label": label, "episodes": 0, "passes": 0,
                                          "judge_parse": None, "_latest": ""})
            g["episodes"] += 1
            g["passes"] += int(bool((r.get("verdict") or {}).get("success")))
            started = str(r.get("started_at") or "")
            if started >= g["_latest"]:
                g["_latest"] = started
                g["judge_parse"] = r.get("judge_parse")
        ordered = sorted(groups.values(), key=lambda g: g["_latest"], reverse=True)
        links[t["name"]] = [{k: v for k, v in g.items() if k != "_latest"} for g in ordered]
    return links
```

In `snapshot`, replace the two task lines with:

```python
    links = link_runs(root, [d.name for d in task_dirs])
    current = runtime_digest()
    tasks = [task_record(d, root, links[d.name], current_digest=current) for d in task_dirs]
    for name, campaigns in link_trajectories(index, tasks).items():
        next(t for t in tasks if t["name"] == name)["campaigns"] = campaigns
```

- [ ] **Step 4: Run the tests, lint, full suite**

Run: `$PY -m pytest forge/tests/test_embed_logs.py -q -p no:cacheprovider && $PY -m ruff check forge scripts && $PY -m pytest -q -p no:cacheprovider | tail -2`
Expected: green.

- [ ] **Step 5: Commit**

```bash
git add scripts/embed_logs.py forge/tests/test_embed_logs.py
git commit -m "The task index reads provenance, judges currency, and links each Gaia2 task to its campaigns"
```

---

### Task 7: The Tasks view follows

**Files:**
- Modify: `trajectory_viewer.html` — state vars near line 487; `renderTasks` (line 1259); `wireSearch` (line 1326); `renderTaskDetail` (line 1342)
- Modify: `DESIGN.md` lines 235-237 and 267-268 (the "no caller" sentences)

**Interfaces:**
- Consumes: task records with `campaigns`, `current`, `judge_parse` (Task 6); `badge(kind, label)`, `ICONS.warn`, `shortScenario`, `tab`, `detail`, `campaignSel`, `issueFilter`, `pendingQuery`, `render()`, `openDetail(i)`, `sessions`, `byKind`, `esc`, `$` — all existing.

- [ ] **Step 1: State**

Next to `let campaignSel = null;` (line 494) add:

```js
let taskSubstrate = "*";   // the Tasks view's substrate filter; "*" is all
```

- [ ] **Step 2: `wireSearch` takes a row predicate**

Change the signature to `function wireSearch(fbar, trs, noun, keep = () => true)` and the hit line to

```js
      const hit = (!q || tr.dataset.text.includes(q)) && keep(tr);
```

and add, after `fbar.addEventListener("input", apply);`:

```js
  fbar.addEventListener("change", apply);
```

- [ ] **Step 3: `renderTasks`**

Replace the lede paragraph and filter bar with:

```js
  const stale = tasks.filter(s => s.data.current === false).length;
  content.insertAdjacentHTML("beforeend",
    `<h2 class="sec">Tasks</h2>
     <p class="lede"><b>${tasks.length}</b> task${tasks.length === 1 ? "" : "s"}: ${
       [...bySub].map(([k, n]) => `${n} ${SUBSTRATE_NAMES[k] || k}`).join(", ")}. Each is a
     directory under <span class="mono">tasks/</span> a container runs. A Gaia2 task is one
     cell of the campaign grid, rendered by the campaign itself; its campaign episodes are
     counted beside it, and its Harbor runs under <span class="mono">jobs/</span>, if any,
     are linked beneath it.${stale ? ` <b>${stale}</b> ${stale === 1 ? "is" : "are"} stale:
     the shipped runtime, contract or judge parse lags the source; re-render with
     <span class="mono">python -m forge.gaia2.cli render --all</span>.` : ""}</p>
     <div class="panel-title">The pool
       <span class="sub">— click a row for its instruction, campaigns and runs</span></div>`);

  const fbar = document.createElement("div");
  fbar.className = "filterline";
  fbar.innerHTML = `<span>substrate
      <select aria-label="substrate">${
        [["*", "all"], ...[...bySub.keys()].sort().map(k => [k, SUBSTRATE_NAMES[k] || k])]
          .map(([v, l]) => `<option value="${esc(v)}"${v === taskSubstrate ? " selected" : ""}>${esc(l)}</option>`).join("")
      }</select></span>
    <span>restrict to
      <input type="search" placeholder="any text" aria-label="filter tasks"></span>
    <span class="count"></span>`;
  $("select", fbar).addEventListener("change", e => { taskSubstrate = e.target.value; });
  content.appendChild(fbar);
```

In the table: change the header row to

```js
      <th>task</th><th>substrate</th><th>configuration</th><th>target</th>
      <th>roster</th><th>difficulty</th><th>contract</th><th>campaigns</th><th>runs</th>
```

and inside the row builder, after `const runs = ...;` add

```js
      const cs = d.campaigns || [];
      const camp = cs.length
        ? `${esc(cs[0].label)} · ${cs[0].passes} of ${cs[0].episodes} passed${
            cs.length > 1 ? ` <span class="tag">+${cs.length - 1} more</span>` : ""}`
        : `<span class="dim">—</span>`;
```

then give the `<tr>` a `data-sub="${esc(d.substrate || "other")}"` attribute, change the contract cell to

```js
        <td class="mono sm">${dash(d.contract_version)}${d.current === false ? " " + badge("warn", "stale") : ""}</td>
```

and insert `<td>${camp}</td>` before `<td>${runs}</td>`. Finally change the wiring line to

```js
  wireSearch(fbar, trs, "tasks", tr => taskSubstrate === "*" || tr.dataset.sub === taskSubstrate);
```

- [ ] **Step 4: `renderTaskDetail`**

In the facts bar, after the `contract` span add

```js
      <span>parse <b class="mono">${esc(dash(d.judge_parse))}</b></span>
      ${d.current === false ? `<span>${badge("warn", "stale")}</span>` : ""}
```

After the description paragraph and before the Harbor-runs panel, insert the campaigns panel:

```js
  const cs = d.campaigns || [];
  if (d.substrate === "gaia2") {
    content.insertAdjacentHTML("beforeend",
      `<div class="panel-title">Campaign episodes of this cell
         <span class="sub">— ${cs.length ? "click a campaign to open its runs" : "none yet"}</span></div>`);
    if (cs.length) {
      const twrap = document.createElement("div");
      twrap.className = "tabwrap";
      twrap.innerHTML = `<table class="tab"><thead><tr>
          <th>campaign</th><th class="n">episodes</th><th class="n">passed</th><th>parse</th>
        </tr></thead><tbody>${
        cs.map(c => `<tr class="click" tabindex="0" data-label="${esc(c.label)}">
          <td>${esc(c.label)}</td>
          <td class="n">${c.episodes}</td>
          <td class="n">${c.passes}</td>
          <td class="mono sm">${esc(c.judge_parse || STOCK_PARSE)}</td></tr>`).join("")
        }</tbody></table>`;
      twrap.querySelectorAll("tr.click").forEach(tr => tr.onclick = () => {
        tab = "runs"; detail = null; campaignSel = tr.dataset.label;
        issueFilter = null; pendingQuery = shortScenario(d.target); render();
      });
      content.appendChild(twrap);
    }
  }
```

Change the Harbor-runs panel's `<span class="sub">` text so a task with no runs says `none under jobs/` only for AppWorld and `no Harbor run yet` otherwise:

```js
       <span class="sub">— ${runs.length ? "click a row for its verifier ledger"
         : d.substrate === "gaia2" ? "no Harbor run yet" : "none under jobs/"}</span></div>`);
```

- [ ] **Step 5: DESIGN.md**

Lines 235-237 currently read: "`--warn` and the `.badge.warn` rule are defined so the status set is complete in all three theme scopes, but nothing on the shipped page paints a bare warn mark: no rule reads `var(--warn)` and nothing calls `badge("warn", …)`." Change the last clause to: "no rule reads `var(--warn)`, and the one caller of `badge("warn", …)` is the Tasks view's *stale* badge, which is fill plus ink plus a word, never a bare mark."

Lines 267-268 currently end: "`.badge.warn` is defined for the same completeness reason and currently has no caller." Change to: "`.badge.warn` has one caller: the Tasks view's *stale* badge (a Gaia2 task whose provenance lags the runtime), which, like every badge, is fill plus ink plus a word."

- [ ] **Step 6: Parse check and tests**

```bash
SCRATCH=$(mktemp -d)
$PY - "$SCRATCH/viewer_check.js" <<'EOF'
import re, pathlib, sys
html = pathlib.Path("trajectory_viewer.html").read_text()
scripts = [m.group(1) for m in re.finditer(r"<script(?![^>]*application/json)[^>]*>(.*?)</script>", html, re.S)]
pathlib.Path(sys.argv[1]).write_text("\n".join(scripts))
print("script blocks:", len(scripts))
EOF
osascript -l JavaScript -e "var s = \$.NSString.stringWithContentsOfFileEncodingError('$SCRATCH/viewer_check.js', 4, null); new Function(ObjC.unwrap(s)); 'parses'"
$PY -m pytest forge/tests/test_viewer.py forge/tests/test_embed_logs.py -q -p no:cacheprovider | tail -2
```

Expected: `parses`; tests green. Then open the page in a browser (`open trajectory_viewer.html`): the Tasks tab shows the substrate select, a campaigns column, and, since the embedded snapshot predates this branch, no stale badges (records without `current` behave as null). That is expected: the snapshot is refreshed on `main` after the merge, when the v7 rollouts are present.

- [ ] **Step 7: Commit**

```bash
git add trajectory_viewer.html DESIGN.md
git commit -m "Tasks view: substrate filter, campaign counts per cell, and a stale badge"
```

---

### Task 8: The record follows

**Files:**
- Modify: `README.md` lines 232 and 234, and lines 346-352
- Modify: `PRODUCT.md` line 22-25 (the viewer surface bullet)

- [ ] **Step 1: README**

Line 234, replace `| \`tasks/\` | rendered Harbor tasks |` with:

```
| `tasks/` | rendered Harbor tasks; for Gaia2, the whole campaign grid — one task per cell, written by the campaign before it runs and by `python -m forge.gaia2.cli render --all`; `tasks/MANIFEST.json` lists it, and a task whose shipped runtime, contract or judge parse lags the source fails `forge/tests/test_gaia2_tasks_current.py` |
```

Line 232 (the viewer row): change "every task with its Harbor runs" to "every task with its campaign episodes and Harbor runs".

Lines 346-352: change "every task under `tasks/` with its Harbor runs linked" to "every task under `tasks/` with its campaign episodes and Harbor runs linked, and a stale badge on any Gaia2 task rendered from an older runtime".

- [ ] **Step 2: PRODUCT.md**

In the viewer bullet, change "shipped-task verifier breakdowns" to "shipped tasks with their campaign episodes and verifier breakdowns".

- [ ] **Step 3: Verify the docs tests and commit**

Run: `$PY -m pytest forge/tests/test_docs_honesty.py forge/tests/test_viewer.py -q -p no:cacheprovider | tail -2`

```bash
git add README.md PRODUCT.md
git commit -m "Record that the campaign renders the grid and a stale task fails the suite"
```

---

## After the last task

The branch is finished by superpowers:finishing-a-development-branch. Two facts for that step:

- The v7 campaign runs in the main checkout and, when it exits, rewrites the embedded snapshot in `trajectory_viewer.html` there as an uncommitted change. Before merging, commit that refresh on `main` (`git add trajectory_viewer.html && git commit -m "Snapshot after the v7 campaign"`), then merge; then run `$PY -m scripts.embed_logs` on `main` so the snapshot carries the new task fields, and commit that.
- Do not merge while `pgrep -f scripts.gaia2_campaign` still finds the campaign.
