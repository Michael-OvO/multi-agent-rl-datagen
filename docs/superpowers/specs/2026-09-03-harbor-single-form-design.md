# Harbor as the single shipped form — design

Date: 2026-09-03. Status: approved in conversation; this file is the record.

## Decisions already taken

Michael answered three questions and approved the design. They bind this
spec and the plan written from it:

1. **Harbor is the shipped form; the campaign stays the runner.** The
   campaign keeps running cells in-process for measurement, and every cell
   it runs is also rendered as a Harbor task from the same runtime, in the
   same run.
2. **Every cell of the Gaia2 grid is rendered and tracked in git.** 132
   tasks, roughly 2.8 MB each, about 370 MB under `tasks/`.
3. **AppWorld stays as it is.** Its package, tasks, run logs, sweep files
   and tests are untouched. An earlier draft of this design removed it; that
   was withdrawn because it saves almost nothing (9 MB of tasks, 1.2 MB of
   logs) next to the Gaia2 grid this design adds.

## Why

The repo has two forms of the same Gaia2 multi-agent task. The campaign
(`scripts/gaia2_campaign.py` → `scripts/gaia2_cell_run.py` →
`forge/gaia2/runtime.py`) runs a scenario in one local process and has
produced every judged episode the repo holds. The renderer
(`forge/gaia2/harbor.py`) writes the same scenario and constraint object into
a Harbor task whose sidecar container carries the runtime verbatim. The
dependency runs one way: nothing on the campaign path imports the renderer;
the renderer imports the runtime. So there is one implementation and one
packaging step, and the packaging step has drifted: the three rendered tasks
under `tasks/gaia2-*` carry `objective-actions-v1` while the campaign runs
`objective-actions-v3` and `case-insensitive-v1`, and none of the three has
ever been run.

Harbor stays because the trainer needs an executable environment, not a
transcript. The fix is to make the renderer a step the campaign cannot skip,
and to make a stale task a test failure.

## Current facts the design rests on

- `tasks/` is tracked: 177 files, 9.1 MB. Six `appworld-*` tasks, three
  `gaia2-*-scenario_universe_30_68r6vs` tasks, one `parallel-scheduling-0003`
  task from the older `forge/maf/` generator.
- A Gaia2 task is 2.8 MB, of which `environment/scenario.json` is 2.5 MB
  (the world, byte-identical to the dataset file so a reviewer can diff it),
  `environment/maf_gaia2/` 100 KB, `environment/maf_appworld/` 60 KB.
- `gaia2_data/` (1.1 GB) is git-ignored and re-fetchable; `output/rollouts/`
  is tracked as paid evidence.
- The campaign grid is `GRID = (None, DISCOVERY, CONTEXT_TRANSFER,
  DELEGATION_ECONOMY)` over every admitted scenario in
  `sweep/gaia2_cells.json` and `sweep/gaia2_cells_adaptability.json` with a
  fetched file: 33 scenarios × 4 = 132 cells. A cell's task name is
  `gaia2-{config.label}-{scenario_id}`; the control label is
  `open-docs-binf`. The grid logic lives only in `scripts/gaia2_campaign.py`
  (`scenario_paths()`, `eligible()`, and the job-building loop in `main()`).
- `write_task(scenario_path, scenario_id, constraints, out_dir, token)` in
  `forge/gaia2/harbor.py` is the renderer's only entry. `token` is drawn from
  `secrets.token_hex(16)` per render, lands in
  `environment/docker-compose.yaml` (`MAF_VERIFIER_TOKEN`) and
  `tests/verifier_token.txt`, so two renders of the same cell never match.
  `VERBATIM_COPIES` maps every destination the task receives byte-for-byte to
  its source; `test_gaia2_harbor.py` guards that map on one fixture render.
- `python -m forge.gaia2.cli render --scenario <path>` renders one scenario's
  three ability cells (not the control cell) with random tokens.
- A trajectory record carries `scenario_id`, `label` (the campaign), and
  `config` (the constraint label, e.g. `open-docs-binf`, `star-docs-b6`).
- The viewer's task index (`scripts/embed_logs.py: task_record`) reads
  `task.toml` and `instruction.md` and attaches Harbor runs found under
  `jobs/**/verifier/breakdown.json` through `link_runs`. All 22 linked runs
  are AppWorld; no Gaia2 task has a Harbor run.

## Design

### 1. Rendering is deterministic

**Token.** `forge/gaia2/harbor.py` gains
`derive_token(scenario_id: str, label: str) -> str` returning
`hashlib.sha256(f"{scenario_id}|{label}|{OBJECTIVE_ACTION_CONTRACT_VERSION}|{JUDGE_PARSE_VERSION}".encode()).hexdigest()[:32]`.
The token is public by construction (it sits in the task directory) and
gates only the sidecar's `/state` endpoint; determinism costs nothing. The
`write_task` signature keeps its `token` parameter; the renderer's callers
pass `derive_token(...)`. The existing test that the token stays out of the
agent's reach keeps passing.

**Write-if-changed.** Every file the renderer writes goes through one helper
that reads the existing bytes first and writes only when they differ. A
re-render of an unchanged cell touches nothing; a re-render after a runtime
change produces a git diff of exactly the files whose content changed.

**Provenance.** Each Gaia2 task gets `provenance.json` at its root:

```json
{
  "scenario_id": "scenario_universe_30_68r6vs",
  "config": "star-docs-binf",
  "objective_action_contract": "objective-actions-v3",
  "judge_parse": "case-insensitive-v1",
  "runtime_digest": "3f1c…"
}
```

`runtime_digest` is `runtime_digest()`, a public function in
`forge/gaia2/harbor.py`: the sha256 over the bytes of every
`VERBATIM_COPIES` source, concatenated in manifest order. It is
content-addressed, so it changes when and only when the shipped runtime
changes. The drift test and the viewer call the same function.

### 2. The grid lives in one place

`forge/gaia2/grid.py`, new, provides

```python
@dataclass(frozen=True)
class Cell:
    scenario_id: str
    scenario_path: Path
    constraints: Constraints
    soft_judge: bool

    @property
    def task_name(self) -> str:  # "gaia2-{constraints.label}-{scenario_id}"

def cells(root: Path, *, scripted_only: bool = False,
          economy_target: int | None = None,
          economy_target_offset: int = 0) -> list[Cell]
```

Its body is the current `scenario_paths()`, `eligible()` and job-building
loop of `scripts/gaia2_campaign.py`, moved without change of behaviour: the
same two cell files, the same admission, the same `GRID`, the same economy
target arithmetic. The campaign, the render command and the drift test all
call it, so they cannot disagree about what the grid is. The campaign's
`--dry-run` listing and its "already done" skip keep working on the `Cell`
objects.

### 3. Rendering is folded into the campaign

**Manifest.** Rendering the grid writes `tasks/MANIFEST.json`, tracked: a
list of `{"name", "scenario_id", "config", "soft_judge"}` for every cell,
sorted by name. It is the grid as rendered, readable on a clone that has no
`gaia2_data`.

**The campaign renders before it runs.** In `scripts/gaia2_campaign.py`,
for every cell returned by `cells()`, including cells skipped as already
done, the campaign calls `write_task` with the derived token into
`ROOT / "tasks"` before submitting any job, then writes the manifest. There
is no flag to skip rendering. `--dry-run` lists cells and renders nothing.

**The render command.** `python -m forge.gaia2.cli render --all` renders the
whole grid and the manifest without running anything, taking the same
`--scripted-only`, `--economy-target` and `--economy-target-offset` options
the campaign takes. The existing `render --scenario <path>` form stays,
renders the four grid cells for that scenario (it renders three today; the
control cell is added so the two forms agree), and uses the derived token.

**Re-render of the three stale tasks.** The first `render --all` on this
branch replaces `tasks/gaia2-*-scenario_universe_30_68r6vs` with current
renders and adds the other 129. This needs `gaia2_data`; in the worktree it
is a symlink to the main checkout's directory, which is an ignored path.

### 4. Drift is a test failure

`forge/tests/test_gaia2_tasks_current.py`, runnable on a clone without
`gaia2_data`:

- `tasks/MANIFEST.json` exists; every entry names a directory under
  `tasks/`; every `tasks/gaia2-*` directory is an entry.
- For every Gaia2 task: each `VERBATIM_COPIES` destination equals its source
  byte-for-byte (the guard that exists today, applied to every shipped task
  rather than one fixture render).
- For every Gaia2 task: `instruction.md` contains `OBJECTIVE_ACTION_CONTRACT`
  and `OBJECTIVE_ACTION_CONTRACT_VERSION`; `provenance.json` carries the
  current contract version, the current `JUDGE_PARSE_VERSION`, and a
  `runtime_digest` equal to `runtime_digest()`.
- For every Gaia2 task: `tests/verifier_token.txt` equals
  `derive_token(scenario_id, config)`.
- For every Gaia2 task, only when `gaia2_data` is present:
  `environment/scenario.json` is byte-identical to the dataset file.

Change the runtime without re-rendering and the suite goes red; the
assertion message names `python -m forge.gaia2.cli render --all` as the fix.
`test_gaia2_harbor.py` keeps its fixture-based tests. AppWorld tasks are not
covered by this test; they keep the tests they have.

### 5. The viewer follows the tasks

In `scripts/embed_logs.py`:

- `link_runs` stays for Harbor runs under `jobs/`.
- New `link_trajectories(index_rows, tasks)`: a trajectory belongs to a task
  when its `scenario_id` equals the task's and its `config` field equals the
  task's config. Each Gaia2 task's `campaigns` field becomes a list grouped by
  campaign label: `{"label", "episodes", "passes", "judge_parse"}`, newest
  label first.
- `task_record` reads `provenance.json` when present and records
  `judge_parse`, `runtime_digest`, and `current` (true when the digest equals
  `runtime_digest()` computed at snapshot time, false when it differs, null
  when there is no provenance file, as for AppWorld tasks).

In `trajectory_viewer.html`, under the existing DESIGN.md rules:

- A Gaia2 task shows its per-campaign episode and pass counts, each count
  linking to the runs it stands for. The existing Harbor-runs list stays for
  tasks that have runs.
- A task whose `current` is false carries a badge, colour plus icon plus the
  word "stale"; a task whose `current` is null carries nothing. The Tasks
  lede states how many tasks are stale and names the render command.
- The task list gains a substrate filter with the values already in
  `SUBSTRATE_NAMES`, so the 132 Gaia2 tasks and the AppWorld tasks can be
  viewed apart. Default: all.

`README.md` and `PRODUCT.md`: the `tasks/` row reads "rendered Harbor tasks;
for Gaia2, the whole campaign grid, one task per cell, written by the
campaign and by `forge.gaia2.cli render --all`; a stale task fails the
suite". `DESIGN.md` is unchanged unless the stale badge needs a token it
does not have; the existing badge vocabulary is expected to suffice.

### 6. Order of work and constraints

1. Deterministic renderer: `derive_token`, write-if-changed, `provenance.json`,
   `runtime_digest()`.
2. `forge/gaia2/grid.py`; campaign and render command call it; manifest;
   `render --all`.
3. Campaign fold-in.
4. Drift test; then `render --all` producing the 132 tasks, committed.
5. Viewer and docs.

Constraints that bind every task:

- All work happens in the worktree
  `.claude/worktrees/harbor-single-form` on branch
  `worktree-harbor-single-form`. Nothing merges into the main checkout while
  the v7 campaign runs there, because every v7 cell imports the runtime from
  that checkout when it spawns.
- Tests run with the main checkout's interpreter:
  `/Users/michael/Documents/Github/multi-agent-rl-datagen/.venv/bin/python -m pytest`
  from the worktree. Gaia2 runtime code that touches `are.*` is never
  imported under that interpreter. Ruff must stay clean. The viewer's script
  must parse under `osascript -l JavaScript`.
- Moved code is moved, not rewritten: the plan checks the grid move with a
  diff that ignores import lines and names.
- No new `--` design tokens in the viewer; badges are colour plus icon plus
  word; the page stays one self-contained file.
- Nothing under `forge/appworld/`, `tasks/appworld-*`, `jobs/` or
  `sweep/appworld_*` changes.

### 7. Out of scope

- Running the rendered tasks with the Harbor tool.
- A gate that decides which cells are worth training on.
- Removing or relocating anything AppWorld.
- `forge/maf/`, `forge/factory/`, the `forge gen` command and the
  `parallel-scheduling-0003` task.
