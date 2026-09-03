# Harbor as the single shipped form — design

Date: 2026-09-03. Status: approved in conversation; this file is the record.

## Decisions already taken

Michael answered three questions and approved the design. They bind this
spec and the plan written from it:

1. **Harbor is the shipped form; the campaign stays the runner.** The
   campaign keeps running cells in-process for measurement, and every cell
   it runs is also rendered as a Harbor task from the same runtime, in the
   same run.
2. **Every cell of the grid is rendered and tracked in git.** 132 tasks,
   roughly 2.8 MB each, about 370 MB under `tasks/`.
3. **Only Gaia2. AppWorld is discarded.** Its paid evidence is archived,
   not deleted.

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
  `open-docs-binf`.
- `write_task(scenario_path, scenario_id, constraints, out_dir, token)` in
  `forge/gaia2/harbor.py` is the renderer's only entry. `token` is drawn from
  `secrets.token_hex(16)` per render, lands in
  `environment/docker-compose.yaml` (`MAF_VERIFIER_TOKEN`) and
  `tests/verifier_token.txt`, so two renders of the same cell never match.
- The Gaia2 runtime imports from the AppWorld package exactly:
  `forge.appworld.partition` (`Constraints`, `Topology`, `Visibility`,
  `control_for`), `forge.appworld.runtime` (`chat`, `execution_feedback`,
  `NO_ANSWER`, `OUT_OF_STEPS`), and, via `forge/abilities.py`,
  `forge.appworld.validity` (`Cell`, `Yield`, `is_control`). The renderer
  imports `forge.appworld.harbor._difficulty` and ships
  `forge/appworld/container/verify.py` as the task verifier. The sidecar
  `Dockerfile.sidecar` copies `maf_appworld` to `/opt/maf/forge/appworld` so
  those imports resolve inside the container; `SIDECAR_APPWORLD_MODULES =
  ("__init__.py", "partition.py", "runtime.py", "sandbox.py")`, where
  `sandbox.py` (823 lines) is pulled in only because `appworld/runtime.py`
  imports it at module level. `chat` uses `DEFAULT_MODEL`, `_RETRYABLE`,
  `_NO_TEMPERATURE` and `require_specialist_parity` from `forge.models`;
  `execution_feedback` uses nothing but builtins.
- AppWorld evidence: `jobs/` (288 tracked files, 1.2 MB, eleven Harbor job
  directories, all AppWorld) and twelve `sweep/appworld_*.json` files.
  `WRITEUP.md` mentions AppWorld 45 times, mostly in §4 "What is built" and
  §7; `docs/iteration_three_abilities.md` 11 times. README, PRODUCT and
  DESIGN mention it zero times.
- The viewer's task index (`scripts/embed_logs.py: task_record`) reads
  `task.toml` and `instruction.md` and attaches Harbor runs found under
  `jobs/**/verifier/breakdown.json` through `link_runs`. All 22 linked runs
  are AppWorld.

## Design

### 1. `forge/team/`: what both the campaign and a shipped task need

A new substrate-neutral package. Every file is a move, not a rewrite; the
plan verifies by diff that moved code is byte-identical except for import
lines.

| New file | Provenance | Contents |
|---|---|---|
| `forge/team/partition.py` | `forge/appworld/partition.py`, verbatim, plus `difficulty()` | `Constraints`, `Topology`, `Visibility`, `control_for`, `Constraints.label`; `difficulty(c)` is `_difficulty` from `forge/appworld/harbor.py`, renamed public |
| `forge/team/validity.py` | `forge/appworld/validity.py`, verbatim | `Cell`, `Yield`, `is_control` and whatever else the module holds |
| `forge/team/chat.py` | extracted from `forge/appworld/runtime.py` | `DEFAULT_MODEL`, `_RETRYABLE`, `_NO_TEMPERATURE`, `chat`, `execution_feedback`, `NO_ANSWER`, `OUT_OF_STEPS`; imports `require_specialist_parity` from `forge.models` and nothing from any sandbox |
| `forge/team/verify.py` | `forge/appworld/container/verify.py`, verbatim | the Harbor verifier that computes nothing and reads the sidecar's `/state` |
| `forge/team/__init__.py` | new, docstring only | names the package's purpose: the team protocol shared by every substrate |

Import sites that change: `forge/gaia2/runtime.py`, `forge/gaia2/render.py`,
`forge/abilities.py`, `forge/gaia2/harbor.py`, `scripts/gaia2_campaign.py`,
`scripts/gaia2_cell_run.py`, and every surviving test that imports from
`forge.appworld`. After this step `grep -rn "forge.appworld" forge scripts`
returns nothing.

### 2. AppWorld is removed

Deleted outright:

- `forge/appworld/` (the whole package, including `container/`).
- `tasks/appworld-star-docs-binf-2a163ab_{1,2,3}` and
  `tasks/appworld-star-names-binf-2a163ab_{1,2,3}`.
- `scripts/appworld_knob_sweep.py`, `scripts/appworld_injection_probe.py`,
  `scripts/watch_episode.py` (bound to the AppWorld runtime).
- Test files whose every `forge.*` import is from `forge.appworld` or from a
  deleted script: `test_appworld_harbor.py`, `test_appworld_partition.py`,
  `test_appworld_reference.py`, `test_appworld_runtime.py`,
  `test_appworld_sandbox.py`, `test_appworld_select.py`,
  `test_appworld_sidecar.py`, `test_appworld_team_client.py`,
  `test_seams.py`, `test_knob_sweep.py`.

Rule for the remaining test files that mention AppWorld
(`test_abilities.py`, `test_environment.py`, `test_docs_honesty.py`,
`test_honest_failure.py`, `test_validity.py`, `test_embed_logs.py`,
`test_gaia2_harbor.py`, `test_gaia2_runtime.py`): a file is deleted only if
every `forge.*` import it takes is from `forge.appworld` or a deleted script;
otherwise its imports are repointed at `forge.team` and any test that
exercised AppWorld-only behaviour is removed from it. `test_validity.py`
moves with its module and becomes `test_team_validity.py`.

Archived, content untouched, with `git mv`:

- `jobs/` → `archive/appworld/jobs/`.
- `sweep/appworld_*.json` (twelve files) → `archive/appworld/sweep/`.
- `archive/appworld/README.md`, new: what these are, that they are paid
  rollouts and the only record of what those Harbor runs did, and the date
  of the move.

`WRITEUP.md` and `docs/iteration_three_abilities.md` keep their AppWorld
history. Each section that cites an archived path gets one sentence at its
top: "AppWorld artifacts were archived under `archive/appworld/` on
2026-09-03; the paths below resolve there." Every path either document cites
must still resolve after the move; the plan checks this with a script over
backticked paths, and the docs-honesty test if it already does so.

`.gitignore` loses its `appworld_data/` entry and comment. `forge/maf/`, the
`forge gen` command, `forge/factory/` and `tasks/parallel-scheduling-0003`
are out of scope and untouched.

### 3. Rendering is deterministic and folded into the campaign

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

**Provenance.** Each task gets `provenance.json` at its root:

```json
{
  "scenario_id": "scenario_universe_30_68r6vs",
  "config": "star-docs-binf",
  "objective_action_contract": "objective-actions-v3",
  "judge_parse": "case-insensitive-v1",
  "runtime_digest": "<sha256 over the bytes of every VERBATIM_COPIES source, in manifest order>"
}
```

`runtime_digest` is content-addressed, so it changes when and only when the
shipped runtime changes. `runtime_digest()` is a public function in
`forge/gaia2/harbor.py` so the drift test and the viewer compute the same
value.

**Sidecar manifest.** `SIDECAR_APPWORLD_MODULES` becomes
`SIDECAR_TEAM_MODULES = ("__init__.py", "partition.py", "chat.py")`, shipped
to `environment/maf_team/`; `Dockerfile.sidecar` line 41 becomes
`COPY maf_team /opt/maf/forge/team`; `tests/verify.py` is copied from
`forge/team/verify.py`. `validity.py` is not shipped: nothing in the sidecar
imports it. The sandbox stops travelling.

**Grid in one place.** `forge/gaia2/grid.py` gains
`cells(root: Path, scripted_only: bool = False, economy_target: int | None = None, economy_target_offset: int = 0) -> list[Cell]`
where `Cell` is a dataclass `(scenario_id, scenario_path, constraints, soft)`.
It is the current body of `scripts/gaia2_campaign.py`'s `scenario_paths()`,
`eligible()` and the job-building loop, moved. The campaign and the render
command both call it, so they cannot disagree about what the grid is.

**Manifest.** Rendering the grid also writes `tasks/MANIFEST.json`, tracked:
a list of `{"name", "scenario_id", "config", "soft_judge"}` for every cell,
sorted by name. It is the grid as rendered, readable on a clone that has no
`gaia2_data`.

**The campaign renders before it runs.** In `scripts/gaia2_campaign.py`,
for every cell returned by `cells()`, including cells skipped as already
done, the campaign calls `write_task` with the derived token into
`ROOT / "tasks"` before submitting any job, then writes the manifest. There
is no flag to skip rendering. `--dry-run` still lists cells and renders
nothing.

**The render command.** `python -m forge.gaia2.cli render --all` renders the
whole grid and the manifest without running anything, with the same
`--scripted-only`, `--economy-target` and `--economy-target-offset` options
the campaign takes. The existing single-scenario `render --scenario` form
stays and uses the derived token.

**Re-render of the three stale tasks.** The first `render --all` on this
branch replaces `tasks/gaia2-*-scenario_universe_30_68r6vs` with current
renders and adds the other 129. This needs `gaia2_data`; in the worktree it
is a symlink to the main checkout's directory, which is an ignored path.

### 4. Drift is a test failure

`forge/tests/test_gaia2_tasks_current.py`, runnable on a clone without
`gaia2_data`:

- `tasks/MANIFEST.json` exists; every entry names a directory under
  `tasks/`; every `tasks/gaia2-*` directory is an entry.
- For every task: each `VERBATIM_COPIES` destination equals its source
  byte-for-byte (the guard that exists today, applied to every shipped task
  rather than one fixture render).
- For every task: `instruction.md` contains `OBJECTIVE_ACTION_CONTRACT` and
  `OBJECTIVE_ACTION_CONTRACT_VERSION`; `provenance.json` carries the current
  contract version, the current `JUDGE_PARSE_VERSION`, and a
  `runtime_digest` equal to `runtime_digest()`.
- For every task, only when `gaia2_data` is present: `environment/scenario.json`
  is byte-identical to the dataset file.
- `tests/verifier_token.txt` equals `derive_token(scenario_id, config)`.

Change the runtime without re-rendering and the suite goes red; the message
names the command that fixes it. `test_gaia2_harbor.py` keeps its
fixture-based tests, repointed at `forge.team` where needed.

### 5. The viewer follows the tasks

In `scripts/embed_logs.py`:

- `link_runs` and the `jobs/` walk are removed.
- `task_record` reads `provenance.json` when present and records
  `judge_parse`, `runtime_digest`, and `current: bool` (digest equals
  `runtime_digest()` computed at snapshot time); a task without a provenance
  file records nulls and `current: false`.
- New `link_trajectories(index_rows, tasks)`: a trajectory belongs to a task
  when its `scenario_id` equals the task's and its `config` field, which the
  cell runner stamps with the constraint label (`open-docs-binf`,
  `star-docs-b6`, ...), equals the task's config.
  Each task's `runs` becomes a list grouped by campaign label:
  `{"label", "episodes", "passes", "judge_parse"}`.

In `trajectory_viewer.html`, under the existing DESIGN.md rules:

- The Tasks tab lists the Gaia2 tasks with their per-campaign episode and
  pass counts, linking each count to the runs it stands for.
- A task whose `current` is false carries a badge, colour plus icon plus the
  word "stale", and the lede states how many tasks are stale and the command
  that re-renders them.
- `SUBSTRATE_NAMES` drops AppWorld; the Harbor-runs drawer that showed
  `jobs/` breakdowns is removed.

`README.md` and `PRODUCT.md`: the `tasks/` row reads "the rendered grid, one
Harbor task per campaign cell, written by the campaign and by
`forge.gaia2.cli render --all`; a stale task fails the suite"; the AppWorld
archive gets one line. `DESIGN.md` is unchanged unless the stale badge needs
a token it does not have; the existing badge vocabulary is expected to
suffice.

### 6. Order of work and constraints

1. `forge/team/` and the import repoint, suite green.
2. AppWorld deletion and archive, suite green, docs paths resolve.
3. Deterministic renderer, provenance, manifest, `grid.py`, render command.
4. Campaign fold-in.
5. Drift test; then `render --all` producing the 132 tasks, committed.
6. Viewer and docs.

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
- Moved code is moved, not rewritten: the plan checks each move with a diff
  that ignores import lines.
- No new `--` design tokens in the viewer; badges are colour plus icon plus
  word; the page stays one self-contained file.

### 7. Out of scope

- Running the rendered tasks with the Harbor tool.
- A gate that decides which cells are worth training on.
- `forge/maf/`, `forge/factory/`, the `forge gen` command and the
  `parallel-scheduling-0003` task.
- Rewriting the AppWorld history in `WRITEUP.md` beyond the archive note.
