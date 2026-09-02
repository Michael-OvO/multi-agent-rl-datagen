# Viewer Tracks Every Result Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `trajectory_viewer.html` carry a compact index of every episode ever run, every task in the pool with its Harbor runs linked, and the current campaign's transcripts; refresh itself whenever a producer finishes; and say plainly which parse and which judge scored each verdict and whether the world ended the episode.

**Architecture:** `scripts/embed_logs.py` builds a three-part snapshot -- an `index` of one small record per rollout, a `tasks` list of one record per `tasks/*/` directory with its `jobs/` runs linked, and `files` holding evidence plus one label's full trajectories -- and exposes `refresh()`/`try_refresh()` for the three producer scripts to call. The viewer loads index records as episode sessions that a full trajectory replaces by `path`, task records as a new `task` session kind with its own section and detail view, and gains a campaign picker, a parse stamp, a judge sentence, a stop column and chip, an episode stub branch, and an evidence summary block -- all inside the existing single-file page under every rule in `DESIGN.md`.

**Tech Stack:** Python 3.11 stdlib (`argparse`, `json`, `pathlib`, `re`, `tomllib`), pytest, one hand-written HTML/CSS/JS file. No new dependencies. Spec: `docs/superpowers/specs/2026-08-31-viewer-current-design.md`.

## Global Constraints

- **TDD, always.** Failing test first, watched failing, then minimal code.
- **Run everything with `.venv/bin/python`.** Never `.venv-gaia2`.
- **Green before every commit:** `.venv/bin/python -m pytest -q` and `.venv/bin/python -m ruff check forge scripts`.
- **The viewer stays one self-contained file**: no external stylesheet, script, font or image; no network request; no build step; works from `file://`.
- **Never hand-edit the `#embedded-logs` block or its script tags**; `scripts/embed_logs.py` rewrites it by regex.
- **No new colours, tokens, tiles, cards, hero figures or motion.** The header keeps exactly two actions (`open files`, `theme`) -- pinned by `test_the_header_offers_exactly_two_actions`.
- **Search the viewer's hand-written source through `viewer_source(viewer_html)`** in `forge/tests/test_viewer.py`; searching the raw file hits the embedded JSON.
- **Every status is painted through `badge(kind, label)`** -- colour, icon and word together. A `.tag` is colourless and qualifies; a `.note` is prose. A substrate is a word, never a colour.
- **Monospace is for code, paths and model names, never for prose.**
- **The `ENV_STOP` sentinel is the exact string `"(environment stopped)"`** (`forge/gaia2/runtime.py:82`).
- **Editing `trajectory_viewer.html`** (8.9 MB): use the `Edit` tool with the exact `old_string`s quoted in each step; the embedded JSON must not be touched. Every quoted snippet below is verbatim from the file.
- **No task under `tasks/` is modified.** The Tasks section reads them.
- Commit subjects are sentences in the repository's style (no `feat:` prefixes). Each commit trailer: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

## File structure

| file | responsibility |
|---|---|
| `scripts/embed_logs.py` (modify) | build the snapshot (`index` + `tasks` + `files`), link runs to tasks, `refresh()`, `try_refresh()`, `--label` |
| `forge/tests/test_embed_logs.py` (create) | contract tests for the snapshot shape, task records, run linking, label selection, refusal, refresh |
| `trajectory_viewer.html` (modify) | load index and tasks; campaign picker; parse stamp; judge sentence; stop row, chip and line; stub branch; evidence summary; Tasks section and detail |
| `forge/tests/test_viewer.py` (modify) | source-level contract tests for each viewer change |
| `scripts/gaia2_campaign.py`, `scripts/gaia2_campaign_summary.py`, `scripts/gaia2_credit_probe.py` (modify) | call `try_refresh(args.label)` after their output is written |
| `forge/tests/test_gaia2_campaign.py` (modify) | source-level tests that the producers refresh, and only after a real run |
| `README.md`, `DESIGN.md` (modify) | describe the loading model as it now is |

---

### Task 1: The snapshot -- index of everything, the task pool, transcripts for one label

**Files:**
- Modify: `scripts/embed_logs.py` (whole file)
- Create: `forge/tests/test_embed_logs.py`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `index_record(path, data, root) -> dict`; `task_record(task_dir, root, runs) -> dict`; `link_runs(root, task_names) -> dict[str, list[dict]]`; `newest_label(records) -> str | None`; `snapshot(root=ROOT, label=None) -> dict` with keys `generated`, `labels`, `full_label`, `index`, `tasks`, `files`; `refresh(label=None, root=ROOT) -> Path`; `try_refresh(label=None, root=ROOT) -> None`. Task 9 imports `try_refresh`. Task 2 reads `index`, `tasks`, `files`, `labels`, `full_label`, `generated`. Task 8 reads every field of a task record.

- [ ] **Step 1: Write the failing tests**

Create `forge/tests/test_embed_logs.py`:

```python
"""The snapshot the viewer carries: every episode indexed, every task listed
with its Harbor runs linked, one campaign's transcripts in full.

Measured 2026-08-31: 613 rollouts on disk total 30.5 MB; a compact index of
all of them is 0.39 MB (642 bytes each). Of the 22 Harbor breakdowns under
jobs/, 16 name their task directory in the path and 6 carry the task stem
with its _1/_2/_3 suffix stripped. These tests pin that contract on a tiny
fabricated tree so they run in milliseconds and never read the real files.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from scripts.embed_logs import (
    index_record,
    link_runs,
    newest_label,
    refresh,
    snapshot,
    task_record,
    try_refresh,
)

BLOCK = ('<script type="application/json" id="embedded-logs">'
         '</script>')

TOML = '''schema_version = "1.3"
artifacts = []

[task]
name = "demo/{name}"
description = "{desc}"
keywords = ["multi-agent"]
[[task.authors]]
name = "multi-agent-task-forge"

[metadata]
difficulty = "medium"
category = "agentic"
tags = ["multi-agent"]

[verifier]
timeout_sec = 600.0

[agent]
timeout_sec = 1800.0
'''

APPWORLD_MD = '''# appworld orchestration

You are the **Main agent**.

## Your task

Like the transactions.

## Your team

You may delegate to: `phone`, `venmo`
You know their names only.
'''

GAIA2_MD = '''# gaia2 orchestration

## Objective action contract

Contract version: `objective-actions-v1`.

## Your team

You may delegate to: `Cabs`, `Calendar`, `Messages`
'''

SCHED_MD = '''# parallel-scheduling

## Team roster (worker: skills)
- `w0`: test, code
- `w1`: code

## Subtasks
- `t000`: skill=code
'''


def episode(label, started, *, success=False, stopped=False, events=None,
            judge="gpt-5.6-sol", parse=None):
    d = {
        "kind": "gaia2-episode", "scenario_id": "scenario_universe_21_x",
        "config": "star-docs-binf", "ability": "context-transfer",
        "label": label, "judge": judge, "started_at": started, "seconds": 61.0,
        "main_model": "m", "sub_model": "m", "delegations": 2,
        "specialist_turns": 5, "malformed": 0, "blocked": 0, "false_outages": 0,
        "answer": "(environment stopped)" if stopped else "booked it",
        "verdict": {"success": success, "rationale": "R" * 2000},
        "credit": {"partial_reward": 0.5, "coverage": 1.0, "fidelity": 0.0,
                   "pivot": 3, "pivot_kind": "wrong-arguments"},
        "events": events if events is not None else [
            {"type": "call", "tool": "A__b", "status": "ok"},
            {"type": "call", "tool": "A__c", "status": "error"},
            {"type": "delegation", "calls": [{"tool": "B__d", "status": "refused"}]},
            {"type": "stop", "sim_time": "t", "reason": "Environment stopped",
             "duration": 1000, "time_passed": 313.0, "remaining": 687.0,
             "env_state": "STOPPED"},
        ],
    }
    if parse:
        d["judge_parse"] = parse
    return d


def breakdown(success, partial):
    return {"success": success, "partial": partial, "passes": 2, "failures": 4,
            "delegations": 2, "answer": "completed", "ledger": [{"a": 1}]}


def make_task(root, name, md, desc="A task."):
    d = root / "tasks" / name
    (d / "environment").mkdir(parents=True)
    (d / "tests").mkdir()
    (d / "task.toml").write_text(TOML.format(name=name, desc=desc))
    (d / "instruction.md").write_text(md)
    (d / "tests" / "verify.py").write_text("")
    return d


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    (tmp_path / "output" / "rollouts").mkdir(parents=True)
    (tmp_path / "sweep").mkdir()
    roll = tmp_path / "output" / "rollouts"
    (roll / "a__v6__1.json").write_text(json.dumps(episode("v6", "2026-08-30 17:00:00", stopped=True)))
    (roll / "b__v6__2.json").write_text(json.dumps(episode("v6", "2026-08-30 18:00:00", success=True, parse="case-insensitive-v1")))
    (roll / "c__full__1.json").write_text(json.dumps(episode("full", "2026-07-28 13:00:00")))
    (roll / "d__probe.json").write_text(json.dumps(episode(None, "2026-07-20 09:00:00")))
    (tmp_path / "sweep" / "gaia2_thing.json").write_text(json.dumps({"note": "n", "summary": {"k": 1}, "rows": [{"a": 1}]}))
    # Three tasks: two of one AppWorld family, one Gaia2.
    make_task(tmp_path, "appworld-star-docs-binf-2a163ab_1", APPWORLD_MD)
    make_task(tmp_path, "appworld-star-docs-binf-2a163ab_2", APPWORLD_MD)
    make_task(tmp_path, "gaia2-star-docs-b4-scenario_universe_30_x", GAIA2_MD)
    (tmp_path / "tasks" / "gaia2-star-docs-b4-scenario_universe_30_x" / "environment" / "scenario.json").write_text("{}")
    # Harbor runs in both path shapes seen under jobs/: the task directory
    # named as a segment (exact), and the stem with its suffix stripped
    # (family); plus one stem no task has.
    for p, ok, part in (
        ("final/appworld-star-docs-binf-2a163ab_1/2026-07-15__12-36-00/appworld-star-docs-binf-2a163ab__AAA", True, 1.0),
        ("oracle-1/2026-07-15__12-12-49/appworld-star-docs-binf-2a163ab__BBB", False, 0.333),
        ("stray/2026-07-15__12-00-00/nothing-like-this__CCC", False, 0.0),
    ):
        d = tmp_path / "jobs" / p / "verifier"
        d.mkdir(parents=True)
        (d / "breakdown.json").write_text(json.dumps(breakdown(ok, part)))
    (tmp_path / "trajectory_viewer.html").write_text(f"<html>{BLOCK}</html>")
    return tmp_path


# -- index records ------------------------------------------------------------


def test_an_index_record_is_the_runs_view_s_fields_and_no_events(tree):
    p = tree / "output" / "rollouts" / "a__v6__1.json"
    r = index_record(p, json.loads(p.read_text()), tree)
    assert r["kind"] == "gaia2-episode" and r["index_only"] is True
    assert r["path"] == "output/rollouts/a__v6__1.json"
    assert "events" not in r
    assert r["stop"] == {"time_passed": 313.0, "duration": 1000, "env_state": "STOPPED"}
    assert r["credit"]["pivot_kind"] == "wrong-arguments"
    assert r["verdict"]["success"] is False
    assert len(r["verdict"]["rationale"]) == 1200
    # Faulted calls are counted the way the viewer's countErrors counts them:
    # any status that is neither ok nor malformed, at the top level and
    # inside delegations. Without this a stub reads as "clean".
    assert r["errors"] == 2


def test_a_record_without_an_instrumented_stop_carries_null(tree):
    p = tree / "output" / "rollouts" / "c__full__1.json"
    d = json.loads(p.read_text())
    d["events"] = [{"type": "stop", "sim_time": "t"}]
    assert index_record(p, d, tree)["stop"] is None


def test_the_newest_label_is_the_one_with_the_latest_start():
    recs = [{"label": "full", "started_at": "2026-07-28 13:00:00"},
            {"label": "v6", "started_at": "2026-08-30 17:00:00"},
            {"label": None, "started_at": "2026-09-01 00:00:00"}]
    assert newest_label(recs) == "v6"
    assert newest_label([]) is None


# -- task records and run linking --------------------------------------------


def test_a_task_record_reads_toml_and_the_delegate_line(tree):
    r = task_record(tree / "tasks" / "appworld-star-docs-binf-2a163ab_1", tree, [])
    assert r["kind"] == "forge-task"
    assert r["name"] == "appworld-star-docs-binf-2a163ab_1"
    assert r["path"] == "tasks/appworld-star-docs-binf-2a163ab_1"
    assert (r["substrate"], r["config"], r["target"]) == ("appworld", "star-docs-binf", "2a163ab_1")
    assert r["description"] == "A task." and r["difficulty"] == "medium"
    assert r["verifier_timeout_sec"] == 600.0 and r["agent_timeout_sec"] == 1800.0
    assert r["roster"] == ["phone", "venmo"]
    assert r["contract_version"] is None
    assert r["instruction"].startswith("# appworld orchestration")
    assert "instruction.md" in r["files"] and "task.toml" in r["files"]
    assert r["has_scenario"] is False
    assert r["runs"] == []


def test_a_gaia2_task_record_carries_its_contract_version_and_scenario(tree):
    r = task_record(tree / "tasks" / "gaia2-star-docs-b4-scenario_universe_30_x", tree, [])
    assert (r["substrate"], r["config"], r["target"]) == ("gaia2", "star-docs-b4", "scenario_universe_30_x")
    assert r["roster"] == ["Cabs", "Calendar", "Messages"]
    assert r["contract_version"] == "objective-actions-v1"
    assert r["has_scenario"] is True


def test_a_scheduling_task_reads_its_roster_from_the_bullets(tmp_path):
    d = make_task(tmp_path, "parallel-scheduling-0003", SCHED_MD)
    r = task_record(d, tmp_path, [])
    assert (r["substrate"], r["config"], r["target"]) == ("parallel-scheduling", None, "0003")
    assert r["roster"] == ["w0", "w1"]


def test_a_task_missing_its_files_is_recorded_not_skipped(tmp_path):
    d = tmp_path / "tasks" / "gaia2-star-docs-binf-broken"
    d.mkdir(parents=True)
    r = task_record(d, tmp_path, [])
    assert r["name"] == "gaia2-star-docs-binf-broken"
    assert r["description"] is None and r["instruction"] is None
    assert r["roster"] == [] and r["contract_version"] is None


def test_runs_link_exactly_by_directory_name_and_by_family_otherwise(tree):
    names = ["appworld-star-docs-binf-2a163ab_1", "appworld-star-docs-binf-2a163ab_2",
             "gaia2-star-docs-b4-scenario_universe_30_x"]
    links = link_runs(tree, names)
    one = links["appworld-star-docs-binf-2a163ab_1"]
    assert [(r["match"], r["batch"], r["when"]) for r in one] == [
        ("exact", "final", "2026-07-15__12-36-00"),
        ("family", "oracle-1", "2026-07-15__12-12-49")]
    assert one[0]["success"] is True and one[0]["partial"] == 1.0
    assert one[0]["path"] == ("jobs/final/appworld-star-docs-binf-2a163ab_1/2026-07-15__12-36-00/"
                              "appworld-star-docs-binf-2a163ab__AAA/verifier/breakdown.json")
    two = links["appworld-star-docs-binf-2a163ab_2"]
    assert [r["match"] for r in two] == ["family"], "the suffix-stripped run reaches every _<n> candidate"
    assert links["gaia2-star-docs-b4-scenario_universe_30_x"] == []


def test_an_unlinkable_run_is_reported_and_left_out(tree, capsys):
    link_runs(tree, ["appworld-star-docs-binf-2a163ab_1"])
    assert "nothing-like-this" in capsys.readouterr().out


# -- the snapshot -------------------------------------------------------------


def test_the_snapshot_indexes_every_episode_lists_every_task_and_embeds_one_label(tree):
    snap = snapshot(root=tree)
    assert snap["labels"] == ["full", "v6"]
    assert snap["full_label"] == "v6"
    assert [r["path"].split("/")[-1] for r in snap["index"]] == [
        "d__probe.json", "c__full__1.json", "a__v6__1.json", "b__v6__2.json"]
    assert [t["name"] for t in snap["tasks"]] == [
        "appworld-star-docs-binf-2a163ab_1", "appworld-star-docs-binf-2a163ab_2",
        "gaia2-star-docs-b4-scenario_universe_30_x"]
    assert len(snap["tasks"][0]["runs"]) == 2
    full = [f["path"] for f in snap["files"] if f["path"].startswith("output/")]
    assert full == ["output/rollouts/a__v6__1.json", "output/rollouts/b__v6__2.json"]
    others = {f["path"] for f in snap["files"] if not f["path"].startswith("output/")}
    assert "sweep/gaia2_thing.json" in others
    assert sum(1 for p in others if p.endswith("breakdown.json")) == 3
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", snap["generated"])


def test_an_explicit_label_selects_that_campaign_s_transcripts(tree):
    snap = snapshot(root=tree, label="full")
    assert snap["full_label"] == "full"
    assert [f["path"] for f in snap["files"] if f["path"].startswith("output/")] == [
        "output/rollouts/c__full__1.json"]
    assert len(snap["index"]) == 4, "the index never narrows with --label"


def test_an_unknown_label_is_refused_naming_what_exists(tree):
    with pytest.raises(SystemExit, match=r"v9.*full, v6"):
        snapshot(root=tree, label="v9")


def test_refresh_rewrites_only_the_embedded_block_and_reports(tree, capsys):
    out = refresh(root=tree)
    html = out.read_text()
    assert html.startswith("<html>") and html.endswith("</html>")
    m = re.search(r'id="embedded-logs">(.*?)</script>', html, re.S)
    snap = json.loads(m.group(1).replace("<\\/", "</"))
    assert len(snap["index"]) == 4 and len(snap["tasks"]) == 3 and snap["full_label"] == "v6"
    line = capsys.readouterr().out.strip().splitlines()[-1]
    assert "4 episodes" in line and "2 campaign" in line and "3 tasks" in line and "v6" in line
    again = refresh(root=tree).read_text()
    strip = lambda h: re.sub(r'"generated":"[^"]*"', "", h)
    assert strip(again) == strip(html)


def test_try_refresh_reports_a_failure_and_never_raises(tmp_path, capsys):
    (tmp_path / "output" / "rollouts").mkdir(parents=True)
    try_refresh(root=tmp_path)
    assert "viewer refresh failed" in capsys.readouterr().out
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest forge/tests/test_embed_logs.py -q`
Expected: `ImportError: cannot import name 'index_record' from 'scripts.embed_logs'`

- [ ] **Step 3: Rewrite `scripts/embed_logs.py`**

Replace the whole file with:

```python
"""Refresh the snapshot embedded in trajectory_viewer.html.

    uv run python -m scripts.embed_logs                 # newest campaign in full
    uv run python -m scripts.embed_logs --label v6      # that campaign in full

The page carries its own data: a JSON snapshot in its `#embedded-logs` block,
so opening the file is the workflow. Files can also be dropped on the page or
chosen through its picker. The snapshot has three parts:

  * `index`  -- one compact record for EVERY episode under output/rollouts/,
                every label, every campaign (613 today, 0.39 MB in total):
                the fields the runs view reads, never the transcript.
  * `tasks`  -- one record per directory under tasks/: what it is, what it
                asks, who the Main may delegate to, which contract it shipped
                with, and every Harbor run of it under jobs/, linked.
  * `files`  -- every sweep/*.json and jobs/**/verifier/breakdown.json, plus
                the FULL trajectories of one label: the newest campaign, or
                the one named by --label.

The producers call `try_refresh()` when they finish -- scripts.gaia2_campaign,
scripts.gaia2_campaign_summary, scripts.gaia2_credit_probe -- so the page
follows the results without anyone remembering this command. Run it by hand
only to refresh without a run.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIEWER = ROOT / "trajectory_viewer.html"

#: One file larger than this is a mistake, not a log.
MAX_BYTES = 2_000_000

_BLOCK = re.compile(
    r'(<script type="application/json" id="embedded-logs">).*?(</script>)',
    re.S,
)

_EVIDENCE = ("sweep/*.json", "jobs/**/verifier/breakdown.json")
_SUBSTRATES = ("appworld", "gaia2", "parallel-scheduling")
_WHEN = re.compile(r"^\d{4}-\d{2}-\d{2}__\d{2}-\d{2}-\d{2}$")


# -- episodes -----------------------------------------------------------------


def _faulted(status) -> bool:
    """The viewer's countErrors rule: any status that is neither ok nor
    malformed. Malformed lines have their own counter."""
    return bool(status) and status != "ok" and status != "malformed"


def _count_errors(events: list) -> int:
    n = 0
    for e in events:
        if e.get("type") == "call" and _faulted(e.get("status")):
            n += 1
        if e.get("type") == "delegation":
            n += sum(1 for c in e.get("calls") or [] if _faulted(c.get("status")))
    return n


def index_record(path: Path, data: dict, root: Path) -> dict:
    """The fields the runs view reads for an episode, plus what a stub detail
    view needs -- never the transcript. `index_only` marks it as a stub that a
    full trajectory with the same `path` replaces."""
    events = data.get("events") or []
    stop = next((e for e in reversed(events)
                 if e.get("type") == "stop" and "time_passed" in e), None)
    verdict = data.get("verdict") or {}
    credit = data.get("credit") or {}
    answer = data.get("answer")
    return {
        "kind": "gaia2-episode",
        "index_only": True,
        "path": str(path.relative_to(root)),
        "scenario_id": data.get("scenario_id"),
        "config": data.get("config"),
        "ability": data.get("ability"),
        "label": data.get("label"),
        "judge": data.get("judge"),
        "judge_parse": data.get("judge_parse"),
        "started_at": data.get("started_at"),
        "seconds": data.get("seconds"),
        "main_model": data.get("main_model"),
        "sub_model": data.get("sub_model"),
        "delegations": data.get("delegations"),
        "specialist_turns": data.get("specialist_turns"),
        "malformed": data.get("malformed"),
        "blocked": data.get("blocked"),
        "false_outages": data.get("false_outages"),
        "errors": _count_errors(events),
        "answer": None if answer is None else str(answer)[:160],
        "verdict": {"success": bool(verdict.get("success")),
                    "rationale": str(verdict.get("rationale") or "")[:1200]},
        "stop": ({k: stop.get(k) for k in ("time_passed", "duration", "env_state")}
                 if stop else None),
        "credit": ({k: credit.get(k) for k in
                    ("partial_reward", "coverage", "fidelity", "pivot", "pivot_kind")}
                   if credit else None),
    }


def newest_label(records: list[dict]) -> str | None:
    """The label whose most recent `started_at` is newest; None if no record
    carries a label. Unlabelled probes never win."""
    latest: dict[str, str] = {}
    for r in records:
        label = r.get("label")
        if label is None:
            continue
        started = str(r.get("started_at") or "")
        if label not in latest or started > latest[label]:
            latest[label] = started
    return max(latest, key=lambda k: latest[k]) if latest else None


# -- tasks --------------------------------------------------------------------


def _split_name(name: str) -> tuple[str | None, str | None, str | None]:
    """appworld-{config}-{task_id} | gaia2-{config}-{scenario_id} |
    parallel-scheduling-{n}. Config is the knob label; target is the rest."""
    for sub in _SUBSTRATES:
        if name == sub or name.startswith(sub + "-"):
            rest = name[len(sub) + 1:]
            if sub == "parallel-scheduling":
                return sub, None, rest or None
            # The config is "<visibility>-<topology>-<budget>" or a
            # scenario id follows; the target is the last segment that
            # looks like a task id (2a163ab_1) or scenario id
            # (scenario_universe_30_68r6vs).
            m = re.match(r"^(.*?)-(scenario_universe_.*|[0-9a-f]{7}(?:_\d+)?)$", rest)
            if m:
                return sub, m.group(1) or None, m.group(2)
            return sub, rest or None, None
    return None, None, None


_DELEGATE = re.compile(r"^You may delegate to:\s*(.*)$", re.M)
_TICKS = re.compile(r"`([^`]+)`")
_CONTRACT = re.compile(r"Contract version:\s*`([^`]+)`")


def _roster(md: str) -> list[str]:
    m = _DELEGATE.search(md)
    if m:
        return _TICKS.findall(m.group(1))
    # The scheduling substrate lists workers as bullets under "## Team roster".
    block = re.search(r"^## Team roster[^\n]*\n((?:- .*\n?)+)", md, re.M)
    if block:
        return [t for line in block.group(1).splitlines()
                for t in _TICKS.findall(line)[:1]]
    return []


def task_record(task_dir: Path, root: Path, runs: list[dict]) -> dict:
    """One task in the pool, read from its own files. A directory missing
    task.toml or instruction.md is recorded with nulls, never skipped."""
    name = task_dir.name
    substrate, config, target = _split_name(name)
    toml_path = task_dir / "task.toml"
    meta: dict = {}
    if toml_path.exists():
        try:
            meta = tomllib.loads(toml_path.read_text())
        except tomllib.TOMLDecodeError:
            meta = {}
    md_path = task_dir / "instruction.md"
    md = md_path.read_text() if md_path.exists() else None
    files = sorted(str(p.relative_to(task_dir)) for p in task_dir.rglob("*")
                   if p.is_file())[:60]
    task = meta.get("task") or {}
    md_meta = meta.get("metadata") or {}
    return {
        "kind": "forge-task",
        "name": name,
        "path": str(task_dir.relative_to(root)),
        "substrate": substrate,
        "config": config,
        "target": target,
        "description": task.get("description"),
        "difficulty": md_meta.get("difficulty"),
        "category": md_meta.get("category"),
        "tags": list(md_meta.get("tags") or []),
        "verifier_timeout_sec": (meta.get("verifier") or {}).get("timeout_sec"),
        "agent_timeout_sec": (meta.get("agent") or {}).get("timeout_sec"),
        "roster": _roster(md) if md else [],
        "contract_version": (_CONTRACT.search(md).group(1)
                             if md and _CONTRACT.search(md) else None),
        "instruction": None if md is None else md[:12000],
        "files": files,
        "has_scenario": (task_dir / "environment" / "scenario.json").exists(),
        "runs": runs,
    }


def link_runs(root: Path, task_names: list[str]) -> dict[str, list[dict]]:
    """Which Harbor runs under jobs/ belong to which task.

    Measured over the 22 breakdowns on disk: 16 name their task directory as
    a path segment (exact); 6 -- the oracle-* and resweep batches -- carry the
    stem with its _1/_2/_3 stripped and reach every _<n> candidate (family).
    A run matching nothing is printed and left out; the Shipped-task runs
    view still shows it."""
    names = set(task_names)
    links: dict[str, list[dict]] = {n: [] for n in task_names}
    for bp in sorted(root.glob("jobs/**/verifier/breakdown.json")):
        parts = bp.relative_to(root / "jobs").parts
        try:
            data = json.loads(bp.read_text())
        except json.JSONDecodeError:
            print(f"  skipping {bp.relative_to(root)} (not JSON)")
            continue
        when = next((seg for seg in parts if _WHEN.match(seg)), None)
        entry = {
            "path": str(bp.relative_to(root)),
            "batch": parts[0],
            "when": when,
            "success": bool(data.get("success")),
            "partial": data.get("partial"),
            "delegations": data.get("delegations"),
            "answer": None if data.get("answer") is None else str(data["answer"])[:160],
        }
        exact = next((seg for seg in parts if seg in names), None)
        if exact:
            links[exact].append({**entry, "match": "exact"})
            continue
        stem = parts[-3].split("__")[0] if len(parts) >= 3 else ""
        family = [n for n in task_names if n == stem or n.startswith(stem + "_")]
        if family:
            for n in family:
                links[n].append({**entry, "match": "family"})
        else:
            print(f"  no task for {bp.relative_to(root)} (stem {stem!r})")
    for runs in links.values():
        runs.sort(key=lambda r: (r["match"] != "exact", str(r["when"] or ""), r["path"]))
    return links


# -- the snapshot -------------------------------------------------------------


def snapshot(root: Path = ROOT, label: str | None = None) -> dict:
    index = []
    for p in sorted(root.glob("output/rollouts/*.json")):
        try:
            data = json.loads(p.read_text())
        except json.JSONDecodeError:
            print(f"  skipping {p.relative_to(root)} (not JSON)")
            continue
        if not isinstance(data, dict) or data.get("kind") != "gaia2-episode":
            continue
        index.append(index_record(p, data, root))
    index.sort(key=lambda r: str(r.get("started_at") or ""))
    labels = sorted({r["label"] for r in index if r.get("label")})
    if label is not None and label not in labels:
        raise SystemExit(f"no rollouts carry label {label!r}; labels present: "
                         f"{', '.join(labels) or '(none)'}")
    full_label = label if label is not None else newest_label(index)

    task_dirs = sorted(p for p in (root / "tasks").glob("*") if p.is_dir()) \
        if (root / "tasks").exists() else []
    links = link_runs(root, [d.name for d in task_dirs])
    tasks = [task_record(d, root, links[d.name]) for d in task_dirs]

    files = []
    patterns = ("output/rollouts/*.json",) + _EVIDENCE
    for pattern in patterns:
        for p in sorted(root.glob(pattern)):
            if p.stat().st_size > MAX_BYTES:
                print(f"  skipping {p.relative_to(root)} "
                      f"({p.stat().st_size / 1e6:.1f} MB)")
                continue
            data = json.loads(p.read_text())
            if pattern.startswith("output/rollouts") and (
                    not isinstance(data, dict) or data.get("label") != full_label):
                continue
            files.append({"path": str(p.relative_to(root)), "data": data})
    return {
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "labels": labels,
        "full_label": full_label,
        "index": index,
        "tasks": tasks,
        "files": files,
    }


def refresh(label: str | None = None, root: Path = ROOT) -> Path:
    """Rewrite the viewer's embedded snapshot. Returns the viewer's path."""
    snap = snapshot(root=root, label=label)
    # "</" must not appear literally inside a script element; the escaped
    # solidus is identical JSON.
    payload = json.dumps(snap, separators=(",", ":")).replace("</", "<\\/")
    viewer = root / "trajectory_viewer.html"
    html = viewer.read_text()
    # A function replacement, not a template: the payload is full of JSON
    # escapes ("…") that a template would try to interpret.
    new, n = _BLOCK.subn(lambda m: m.group(1) + payload + m.group(2), html)
    if n != 1:
        raise SystemExit("trajectory_viewer.html has no embedded-logs block; "
                         "the viewer and this script have drifted")
    viewer.write_text(new)
    n_lab = len(snap["labels"])
    print(f"viewer: {len(snap['index'])} episodes indexed across {n_lab} "
          f"campaign{'' if n_lab == 1 else 's'}; {len(snap['tasks'])} tasks; "
          f"transcripts for {snap['full_label']}; {len(new) / 1e6:.1f} MB")
    return viewer


def try_refresh(label: str | None = None, root: Path = ROOT) -> None:
    """For the producers: the results are already on disk and the page is a
    view of them, so a refresh failure is reported on one line, never raised."""
    try:
        refresh(label=label, root=root)
    except Exception as e:  # any failure here must not fail the run that called us
        print(f"viewer refresh failed ({type(e).__name__}: {e}); "
              f"run: uv run python -m scripts.embed_logs"
              f"{'' if label is None else ' --label ' + label}")


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--label", default=None,
                    help="campaign whose transcripts are embedded in full "
                         "(default: the newest)")
    args = ap.parse_args()
    refresh(label=args.label)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest forge/tests/test_embed_logs.py -q`
Expected: `14 passed`

- [ ] **Step 5: Run the suite and lint, then commit**

Run: `.venv/bin/python -m pytest -q && .venv/bin/python -m ruff check forge scripts`
Expected: all passed (`test_embed_logs_block_still_matches_its_rewriter` keeps passing: `_BLOCK` is unchanged); `All checks passed!`

```bash
git add scripts/embed_logs.py forge/tests/test_embed_logs.py
git commit -m "Index every episode and every task in the viewer's snapshot; embed one campaign in full

613 rollouts total 30.5 MB; their index is 0.39 MB. The snapshot now carries
an index record for every episode -- the fields the runs view reads, a
truncated rationale for a stub detail view, the instrumented stop facts, the
shaping signals, and a faulted-call count so a stub never reads as clean --
one record per task under tasks/ with its Harbor runs linked (16 of 22 by the
task directory named in the path, 6 by a suffix-stripped stem reaching every
_<n> candidate), and full trajectories for one label only: the newest
campaign or --label. refresh() rewrites the page and reports one line;
try_refresh() is what the producers call, and it never raises, because the
results are already on disk.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: The viewer loads the index and the tasks; a full trajectory replaces its stub

**Files:**
- Modify: `trajectory_viewer.html` -- the state block (after `let savedScroll = 0;`), `detect`, `sortSessions`, and the `loadSnapshot` IIFE at the end of the script
- Test: `forge/tests/test_viewer.py`

**Interfaces:**
- Consumes: Task 1's snapshot keys `index`, `tasks`, `files`, `labels`, `full_label`, `generated`.
- Produces: module-level `let fullLabel = null;` (Tasks 3 and 6 read it) and `let campaignSel = null;` (Task 3); the session kind `"task"` (Task 8 reads `byKind("task")`).

- [ ] **Step 1: Write the failing tests**

Append to `forge/tests/test_viewer.py`:

```python
# -- the snapshot carries an index of every episode and the task pool ---------


def test_the_snapshot_loader_adds_index_then_tasks_then_files(viewer_html):
    """A full trajectory in `files` must replace the stub with the same path,
    and addSession keeps the LATER entry -- so the index goes in first."""
    source = viewer_source(viewer_html)
    loader = re.search(r"function loadSnapshot\(\) \{(.*?)\n\}\)\(\);", source, re.S)
    assert loader, "the loadSnapshot IIFE moved; update this test's anchor"
    body = loader.group(1)
    assert "snap.index" in body and "snap.tasks" in body and "snap.files" in body
    assert body.index("snap.index") < body.index("snap.tasks") < body.index("snap.files")
    assert "fullLabel = snap.full_label" in body


def test_the_source_line_names_episodes_campaigns_tasks_and_the_full_label(viewer_html):
    source = viewer_source(viewer_html)
    assert "episodes across" in source
    assert "} tasks" in source
    assert "transcripts for" in source


def test_index_stubs_and_the_campaign_selection_are_page_state(viewer_html):
    source = viewer_source(viewer_html)
    assert "let fullLabel = null;" in source
    assert "let campaignSel = null;" in source


def test_task_records_are_their_own_session_kind(viewer_html):
    source = viewer_source(viewer_html)
    assert 'if (data && data.kind === "forge-task") return "task";' in source
    assert "task: 1" in re.search(r"const order = \{(.*?)\};", source).group(1)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest forge/tests/test_viewer.py -k "index_then_tasks or source_line or page_state or own_session_kind" -q`
Expected: 4 failed

- [ ] **Step 3: Add the two state variables**

Edit `trajectory_viewer.html`. Old string (verbatim):

```
let pendingQuery = null;   // a search string the next runs-table render adopts
let savedScroll = 0;
```

New string:

```
let pendingQuery = null;   // a search string the next runs-table render adopts
let savedScroll = 0;
let fullLabel = null;      // the campaign whose transcripts the snapshot embeds
let campaignSel = null;    // null until first render, then a label or "*" for all
```

- [ ] **Step 4: Teach `detect` and `sortSessions` the task kind**

Edit `trajectory_viewer.html`. Old string (verbatim):

```
function detect(data) {
  if (data && data.kind === "gaia2-episode") return "episode";
```

New string:

```
function detect(data) {
  if (data && data.kind === "gaia2-episode") return "episode";
  if (data && data.kind === "forge-task") return "task";
```

Old string (verbatim):

```
  const order = {episode: 0, breakdown: 1, sweep: 2, raw: 3};
```

New string:

```
  const order = {episode: 0, task: 1, breakdown: 2, sweep: 3, raw: 4};
```

- [ ] **Step 5: Load index, then tasks, then files**

Edit `trajectory_viewer.html`. Old string (verbatim):

```
    if (snap && Array.isArray(snap.files) && snap.files.length) {
      for (const f of snap.files) addSession(f.path.split("/").pop(), f.path, f.data);
      sourceLine = `snapshot of ${snap.generated}, ${snap.files.length} artifacts`;
      sortSessions();
    }
```

New string:

```
    const index = snap && Array.isArray(snap.index) ? snap.index : [];
    const tasks = snap && Array.isArray(snap.tasks) ? snap.tasks : [];
    const files = snap && Array.isArray(snap.files) ? snap.files : [];
    if (index.length || tasks.length || files.length) {
      /* Index first: a full trajectory in `files` carries the same path as
         its index stub, and addSession keeps the later entry. */
      for (const r of index) addSession(r.path.split("/").pop(), r.path, r);
      for (const t of tasks) addSession(t.name, t.path, t);
      for (const f of files) addSession(f.path.split("/").pop(), f.path, f.data);
      fullLabel = snap.full_label || null;
      const nLab = (snap.labels || []).length;
      const nEv = files.filter(f => !(f.data && f.data.kind === "gaia2-episode")).length;
      sourceLine = index.length || tasks.length
        ? `snapshot of ${snap.generated} · ${index.length} episodes across ${nLab} campaign${
            nLab === 1 ? "" : "s"} · ${tasks.length} tasks${
            fullLabel ? ` · transcripts for ${fullLabel}` : ""} · ${nEv} evidence files`
        : `snapshot of ${snap.generated}, ${files.length} artifacts`;
      sortSessions();
    }
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest forge/tests/test_viewer.py -q`
Expected: all passed

- [ ] **Step 7: Commit**

```bash
git add trajectory_viewer.html forge/tests/test_viewer.py
git commit -m "Load the snapshot's index as episode stubs a full trajectory replaces, and its tasks

Index records carry kind \"gaia2-episode\" so detect() serves stubs and
transcripts alike; addSession de-duplicates by path and keeps the later
entry, so the index goes in first and the current campaign's full
trajectories replace their stubs with no further logic. Task records are a
session kind of their own. The source line names what the page holds.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: The campaign picker

**Files:**
- Modify: `trajectory_viewer.html` -- `renderRuns`, its opening lines and the `fbar.innerHTML` filter line
- Test: `forge/tests/test_viewer.py`

**Interfaces:**
- Consumes: `fullLabel`, `campaignSel` from Task 2.
- Produces: inside `renderRuns`, `all` (every episode session) and `eps` (the selected set) -- every later computation in `renderRuns` (Tasks 4 and 5) reads `eps`.

- [ ] **Step 1: Write the failing tests**

Append to `forge/tests/test_viewer.py`:

```python
# -- readable across campaigns: one at a time by default ----------------------


def test_the_runs_view_offers_a_campaign_picker_in_the_filter_line(viewer_html):
    source = viewer_source(viewer_html)
    assert 'id="campaignpick"' in source
    assert "all campaigns" in source
    header = re.search(r"<header>(.*?)</header>", viewer_html, re.S).group(1)
    assert "campaignpick" not in header


def test_the_picker_defaults_to_the_embedded_campaign(viewer_html):
    source = viewer_source(viewer_html)
    assert "campaignSel = fullLabel" in source
    assert 'campaignSel === "*"' in source
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest forge/tests/test_viewer.py -k "campaign_picker or defaults_to" -q`
Expected: 2 failed

- [ ] **Step 3: Select the campaign at the top of `renderRuns`**

Edit `trajectory_viewer.html`. Old string (verbatim):

```
function renderRuns(content) {
  const eps = byKind("episode");
  if (!eps.length) {
```

New string:

```
function renderRuns(content) {
  const all = byKind("episode");
  /* Campaigns, newest first by their latest start. The page opens on the
     campaign whose transcripts it carries; "all campaigns" is a choice. */
  const latest = new Map();
  for (const s of all) {
    const l = s.data.label || "(unlabelled)";
    const t = String(s.data.started_at || "");
    if (!latest.has(l) || t > latest.get(l)) latest.set(l, t);
  }
  const labels = [...latest.keys()].sort((a, b) => latest.get(b).localeCompare(latest.get(a)));
  if (campaignSel === null) campaignSel = fullLabel || labels[0] || "*";
  if (campaignSel !== "*" && !latest.has(campaignSel)) campaignSel = labels[0] || "*";
  const eps = campaignSel === "*" ? all
    : all.filter(s => (s.data.label || "(unlabelled)") === campaignSel);
  if (!eps.length) {
```

- [ ] **Step 4: Put the picker first in the filter line**

Edit `trajectory_viewer.html`. Old string (verbatim):

```
  fbar.className = "filterline";
  fbar.innerHTML = `<span>restrict to
      <input type="search" placeholder="any text" aria-label="filter runs"></span>
    <select data-f="verdict" aria-label="verdict"><option value="">any verdict</option>
```

New string:

```
  fbar.className = "filterline";
  fbar.innerHTML = `<span>campaign
      <select id="campaignpick" aria-label="campaign">${
        labels.map(l => `<option value="${esc(l)}"${l === campaignSel ? " selected" : ""}>${
          esc(l)}</option>`).join("")}<option value="*"${
        campaignSel === "*" ? " selected" : ""}>all campaigns</option></select></span>
    <span>restrict to
      <input type="search" placeholder="any text" aria-label="filter runs"></span>
    <select data-f="verdict" aria-label="verdict"><option value="">any verdict</option>
```

Old string (verbatim -- the first occurrence after the filter line above):

```
    <span class="count"></span>`;
  content.appendChild(fbar);

  const hasLabels = eps.some(s => s.data.label);
```

New string:

```
    <span class="count"></span>`;
  content.appendChild(fbar);
  /* The picker changes what the whole view computes from, so it re-renders
     rather than filtering rows; the search box and the dropdowns still
     compose on top of whichever campaign is chosen. */
  $("#campaignpick", fbar).addEventListener("change", e => {
    campaignSel = e.target.value; issueFilter = null; pendingQuery = null; render();
  });

  const hasLabels = eps.some(s => s.data.label);
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest forge/tests/test_viewer.py -q`
Expected: all passed

- [ ] **Step 6: Commit**

```bash
git add trajectory_viewer.html forge/tests/test_viewer.py
git commit -m "Give the runs view a campaign picker, opening on the embedded campaign

With every episode indexed, one grid over six campaigns is texture. The
picker sits first in the filter line -- the header's two actions stay two --
defaults to the campaign whose transcripts the page carries, and offers all
campaigns as a choice. It re-renders the view, so the grid, the chips, the
note and the table all compute from the chosen set.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: The parse stamp and success by judge

**Files:**
- Modify: `trajectory_viewer.html` -- helpers beside `judgeLabel`; the Table 1 block of `renderRuns`; the runs-table row template
- Test: `forge/tests/test_viewer.py`

**Interfaces:**
- Consumes: `eps`, `majorityJudge`, `judgeLabel(j)`, `badge(kind, label)`, `esc()`.
- Produces: `STOCK_PARSE`, `parseLabel(d)`, and inside `renderRuns` `majorityParse` and `judgeSentence`.

- [ ] **Step 1: Write the failing tests**

Append to `forge/tests/test_viewer.py`:

```python
# -- which parse graded each verdict, and success by judge --------------------


def test_the_grid_states_the_majority_parse_and_tags_only_departures(viewer_html):
    source = viewer_source(viewer_html)
    grid = re.search(
        r"-- Table 1: the verdict matrix --\s*\*/(.*?)-- Table 2:", source, re.S)
    assert grid, "the grid-building block moved; update this test's anchors"
    body = grid.group(1)
    assert "parseLabel(" in body and "majorityParse" in body
    assert "badge(" in body and "verdictBadge(" not in body
    assert "gaia2_v6_judge_parse.json" in body
    assert "majorityParse === STOCK_PARSE" in body


def test_the_parse_helpers_default_to_stock(viewer_html):
    source = viewer_source(viewer_html)
    assert 'const STOCK_PARSE = "stock";' in source
    assert "const parseLabel = d => d.judge_parse || STOCK_PARSE;" in source


def test_the_grid_note_states_success_by_judge_as_a_sentence(viewer_html):
    source = viewer_source(viewer_html)
    assert "judgeSentence" in source
    assert "of ${c.total} passed" in source
    assert '=== "scripted" ? 0 : 1' in source


def test_rows_index_their_parse_for_the_search_box(viewer_html):
    source = viewer_source(viewer_html)
    row = re.search(r'data-text="\$\{esc\(JSON\.stringify\(\[(.*?)\]\)', source, re.S)
    assert row, "the runs-table row's data-text moved"
    assert "parseLabel(d)" in row.group(1)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest forge/tests/test_viewer.py -k "majority_parse or parse_helpers or success_by_judge or index_their_parse" -q`
Expected: 4 failed

- [ ] **Step 3: Add the parse helpers beside `judgeLabel`**

Edit `trajectory_viewer.html`. Old string (verbatim):

```
function judgeLabel(
```

New string:

```
/* Which parse read the judge's checker answers. Absent on every trajectory
   before forge/gaia2/judge_parse.py (commit 0a83ccf); "stock" names the
   benchmark's own case-sensitive read, which recorded [[true]] as a
   failure. Stated once as the majority, tagged only where a row departs --
   the same rule the judge tag follows. */
const STOCK_PARSE = "stock";
const parseLabel = d => d.judge_parse || STOCK_PARSE;

function judgeLabel(
```

- [ ] **Step 4: Compute the majority parse and the judge sentence in the grid block**

Edit `trajectory_viewer.html`. Old string (verbatim):

```
  const majorityJudge = [...judgeCounts]
    .sort((a, b) => b[1] - a[1] || String(a[0]).localeCompare(String(b[0])))[0][0];

  const wrap = document.createElement("div");
```

New string:

```
  const majorityJudge = [...judgeCounts]
    .sort((a, b) => b[1] - a[1] || String(a[0]).localeCompare(String(b[0])))[0][0];

  const parseCounts = new Map();
  for (const s of eps) {
    const p = parseLabel(s.data);
    parseCounts.set(p, (parseCounts.get(p) || 0) + 1);
  }
  const majorityParse = [...parseCounts]
    .sort((a, b) => b[1] - a[1] || String(a[0]).localeCompare(String(b[0])))[0][0];

  /* Success split by judge is the only split that means anything on Gaia2:
     the graders score disjoint scenario populations. One clause per judge
     present, scripted first, as prose in the note -- not a tile. */
  const byJudge = new Map();
  for (const s of eps) {
    const j = s.data.judge || "scripted";
    const c = byJudge.get(j) || {passed: 0, total: 0};
    c.total++;
    if (s.data.verdict && s.data.verdict.success) c.passed++;
    byJudge.set(j, c);
  }
  const judgeSentence = [...byJudge]
    .sort((a, b) => (a[0] === "scripted" ? 0 : 1) - (b[0] === "scripted" ? 0 : 1)
      || String(a[0]).localeCompare(String(b[0])))
    .map(([j, c]) => {
      const name = judgeLabel(j);
      return `${name.charAt(0).toUpperCase()}${name.slice(1)}: ${c.passed} of ${c.total} passed.`;
    }).join(" ");

  const wrap = document.createElement("div");
```

- [ ] **Step 5: Tag departures on the grid's marks**

Edit `trajectory_viewer.html`. Old string (verbatim):

```
            const tag = judge !== majorityJudge
              ? `<span class="tag">${judgeLabel(judge)}</span>` : "";
            return `<a class="xref" data-i="${sessions.indexOf(s)}"
              tabindex="0" role="button"
              title="${esc(String(s.data.answer ?? ""))}">${
              badge(okr ? "pass" : "fail", okr ? "pass" : "fail")}${tag}${
```

New string:

```
            const tag = judge !== majorityJudge
              ? `<span class="tag">${judgeLabel(judge)}</span>` : "";
            const ptag = parseLabel(s.data) !== majorityParse
              ? `<span class="tag">${esc(parseLabel(s.data))}</span>` : "";
            return `<a class="xref" data-i="${sessions.indexOf(s)}"
              tabindex="0" role="button"
              title="${esc(String(s.data.answer ?? ""))}">${
              badge(okr ? "pass" : "fail", okr ? "pass" : "fail")}${tag}${ptag}${
```

- [ ] **Step 6: Extend the grid note**

Edit `trajectory_viewer.html`. Old string (verbatim):

```
      default; a mark tagged with a different judge used that judge instead.
      Two marks in one cell are the same run under both judges.</p>`;
```

New string:

```
      default; a mark tagged with a different judge used that judge instead.
      Two marks in one cell are the same run under both judges.
      ${judgeSentence}
      Verdicts were read under ${majorityParse === STOCK_PARSE
        ? `the benchmark's stock parse, which recorded its checker's
           <span class="mono">[[true]]</span> as a failure — see
           <span class="mono">sweep/gaia2_v6_judge_parse.json</span>`
        : `the <span class="mono">${esc(majorityParse)}</span> parse`};
      a mark tagged with a different parse used that parse instead.</p>`;
```

- [ ] **Step 7: Tag departures in the runs table and index the parse for search**

Edit `trajectory_viewer.html`. Old string (verbatim):

```
      const jtag = judge !== majorityJudge
        ? `<span class="tag">${judgeLabel(judge)}</span>` : "";
      return `<tr class="click" data-i="${sessions.indexOf(s)}" tabindex="0"
        data-verdict="${okr ? "ok" : "bad"}"
        data-ability="${esc(d.ability || "control")}"
        data-judge="${esc(judge)}"
        data-issues="${tags}"
        data-text="${esc(JSON.stringify([d.scenario_id, d.config, d.ability,
                        d.judge, d.label, d.answer, d.main_model]).toLowerCase())}">
        <td>${badge(okr ? "pass" : "fail", okr ? "pass" : "fail")}${jtag}</td>
```

New string:

```
      const jtag = judge !== majorityJudge
        ? `<span class="tag">${judgeLabel(judge)}</span>` : "";
      const ptag = parseLabel(d) !== majorityParse
        ? `<span class="tag">${esc(parseLabel(d))}</span>` : "";
      return `<tr class="click" data-i="${sessions.indexOf(s)}" tabindex="0"
        data-verdict="${okr ? "ok" : "bad"}"
        data-ability="${esc(d.ability || "control")}"
        data-judge="${esc(judge)}"
        data-issues="${tags}"
        data-text="${esc(JSON.stringify([d.scenario_id, d.config, d.ability,
                        d.judge, d.label, d.answer, d.main_model,
                        parseLabel(d)]).toLowerCase())}">
        <td>${badge(okr ? "pass" : "fail", okr ? "pass" : "fail")}${jtag}${ptag}</td>
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest forge/tests/test_viewer.py -q`
Expected: all passed (including the pre-existing `test_the_grid_tags_only_the_minority_judge` and `test_the_note_does_not_call_the_scripted_judge_official`)

- [ ] **Step 9: Commit**

```bash
git add trajectory_viewer.html forge/tests/test_viewer.py
git commit -m "Say which parse graded each verdict, and how each judge scored

The majority parse is stated once in the grid's note and only departures
carry a tag -- the rule the judge already follows. When the majority is the
benchmark's stock parse the note says what that parse did to [[true]] and
names the evidence. One computed sentence per judge present gives success by
judge as prose, scripted first.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: The stop row -- an `ended` column and a disjoint chip

**Files:**
- Modify: `trajectory_viewer.html` -- helpers beside `countErrors`; `countErrors` itself; `runStats`; `renderSignals`; the runs-table header and row template
- Test: `forge/tests/test_viewer.py`

**Interfaces:**
- Consumes: `eps`; `runStats(eps)`; `renderSignals(content, stats)`; `issueFilter`.
- Produces: `ENV_STOP`, `wasStopped(d)`, `lastStop(d)`, `endedCell(d)`; `stats.stopped`; the chip key `"stopped"`; the `stopped` token in `data-issues`. Task 6 reuses `wasStopped` and `lastStop`.

- [ ] **Step 1: Write the failing tests**

Append to `forge/tests/test_viewer.py`:

```python
# -- whether the world ended the episode --------------------------------------


def test_the_stop_helpers_read_the_instrumented_stop_row(viewer_html):
    source = viewer_source(viewer_html)
    assert 'const ENV_STOP = "(environment stopped)";' in source
    assert "const wasStopped = d =>" in source
    assert "function lastStop(d)" in source and '"time_passed" in ev[i]' in source
    assert "return d.stop || null;" in source
    assert "function endedCell(d)" in source
    assert "world stopped at ${t}" in source


def test_the_runs_table_has_an_ended_column_between_issues_and_answer(viewer_html):
    source = viewer_source(viewer_html)
    head = re.search(r"<th>issues</th>(.*?)<th>answer</th>", source, re.S)
    assert head and "<th>ended</th>" in head.group(1)
    assert "${endedCell(d)}" in source


def test_stopped_is_a_disjoint_signal_with_its_own_chip(viewer_html):
    source = viewer_source(viewer_html)
    assert 'wasStopped(d) ? "stopped" : ""' in source
    assert "let malformed = 0, blocked = 0, errors = 0, stopped = 0;" in source
    assert 'key: "stopped", kind: "warn"' in source
    assert "stopped by the world" in source
    fn = re.search(r"function countErrors\(d\) \{(.*?)\n\}", source, re.S).group(1)
    assert "answer" not in fn and "ENV_STOP" not in fn


def test_count_errors_reads_a_precomputed_count_like_count_malformed(viewer_html):
    source = viewer_source(viewer_html)
    fn = re.search(r"function countErrors\(d\) \{(.*?)\n\}", source, re.S).group(1)
    assert 'if (typeof d.errors === "number") return d.errors;' in fn
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest forge/tests/test_viewer.py -k "stop_helpers or ended_column or disjoint_signal or precomputed_count" -q`
Expected: 4 failed

- [ ] **Step 3: Add the precomputed error count and the stop helpers**

Edit `trajectory_viewer.html`. Old string (verbatim):

```
function countErrors(d) {
  const faulted = s => s && s !== "ok" && s !== "malformed";
  let n = 0;
```

New string:

```
function countErrors(d) {
  /* An index stub carries no events; the snapshot builder counted its
     faulted calls by this same rule, so read that first -- as countMalformed
     already reads d.malformed. */
  if (typeof d.errors === "number") return d.errors;
  const faulted = s => s && s !== "ok" && s !== "malformed";
  let n = 0;
```

Old string (verbatim):

```
      for (const c of e.calls || []) if (faulted(c.status)) n++;
  }
  return n;
}

function runStats(eps) {
```

New string:

```
      for (const c of e.calls || []) if (faulted(c.status)) n++;
  }
  return n;
}

/* The harness returns this sentinel when the world announced the episode's
   end before the Main did (forge/gaia2/runtime.py ENV_STOP). Not a
   surrender: the agent did not give up, the world moved on. */
const ENV_STOP = "(environment stopped)";
const wasStopped = d => String(d.answer ?? "").trim() === ENV_STOP;

/* The instrumented stop row: reason, duration, time_passed, remaining,
   env_state (commit a59d9bb). Pre-instrumentation runs have a bare stop
   event; index stubs carry the facts as d.stop. The last one wins. */
function lastStop(d) {
  const ev = d.events || [];
  for (let i = ev.length - 1; i >= 0; i--)
    if (ev[i].type === "stop" && "time_passed" in ev[i]) return ev[i];
  return d.stop || null;
}

function endedCell(d) {
  if (d.answer == null) return `<span class="dim">—</span>`;
  if (!wasStopped(d)) return "answered";
  const st = lastStop(d);
  if (!st) return `<span class="warn-text">world stopped</span>`;
  const t = Math.round(st.time_passed);
  const horizon = st.duration != null ? `/${Math.round(st.duration)}` : "";
  return `<span class="warn-text">world stopped at ${t}${horizon} s</span>`;
}

function runStats(eps) {
```

- [ ] **Step 4: Count stopped episodes in `runStats`**

Edit `trajectory_viewer.html`. Old string (verbatim):

```
function runStats(eps) {
  let malformed = 0, blocked = 0, errors = 0;
  for (const s of eps) {
    malformed += countMalformed(s.data);
    blocked += s.data.blocked || 0;
    errors += countErrors(s.data);
  }
```

New string:

```
function runStats(eps) {
  let malformed = 0, blocked = 0, errors = 0, stopped = 0;
  for (const s of eps) {
    malformed += countMalformed(s.data);
    blocked += s.data.blocked || 0;
    errors += countErrors(s.data);
    if (wasStopped(s.data)) stopped++;
  }
```

Old string (verbatim):

```
  return {malformed, blocked, errors, worst};
```

New string:

```
  return {malformed, blocked, errors, stopped, worst};
```

- [ ] **Step 5: Add the chip**

Edit `trajectory_viewer.html`. Old string (verbatim):

```
  if (stats.errors)
    signals.push({key: "errors", kind: "warn",
                  label: `${stats.errors} faulted tool call${stats.errors === 1 ? "" : "s"}`});
```

New string:

```
  if (stats.errors)
    signals.push({key: "errors", kind: "warn",
                  label: `${stats.errors} faulted tool call${stats.errors === 1 ? "" : "s"}`});
  if (stats.stopped)
    signals.push({key: "stopped", kind: "warn",
                  label: `${stats.stopped} stopped by the world`});
```

- [ ] **Step 6: Add the column and the row key**

Edit `trajectory_viewer.html`. Old string (verbatim):

```
      const tags = [mal ? "malformed" : "", blk ? "blocked" : "",
                    err ? "errors" : ""].filter(Boolean).join(" ");
```

New string:

```
      const tags = [mal ? "malformed" : "", blk ? "blocked" : "",
                    err ? "errors" : "", wasStopped(d) ? "stopped" : ""]
                   .filter(Boolean).join(" ");
```

Old string (verbatim):

```
      <th>issues</th><th>answer</th><th class="n">wall&nbsp;s</th>
```

New string:

```
      <th>issues</th><th>ended</th><th>answer</th><th class="n">wall&nbsp;s</th>
```

Old string (verbatim):

```
        <td>${issues ? `<span class="warn-text">${esc(issues)}</span>`
                     : `<span class="dim">clean</span>`}</td>
        <td title="${esc(d.answer ?? "")}">${esc(String(d.answer ?? "").slice(0, 44))}</td>
```

New string:

```
        <td>${issues ? `<span class="warn-text">${esc(issues)}</span>`
                     : `<span class="dim">clean</span>`}</td>
        <td>${endedCell(d)}</td>
        <td title="${esc(d.answer ?? "")}">${esc(String(d.answer ?? "").slice(0, 44))}</td>
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest forge/tests/test_viewer.py -q`
Expected: all passed

- [ ] **Step 8: Commit**

```bash
git add trajectory_viewer.html forge/tests/test_viewer.py
git commit -m "Show whether the world ended each episode, and at what point of its horizon

An ended column reads the instrumented stop row -- 'world stopped at
313/1000 s' -- or says 'world stopped' alone for runs recorded before it
existed. A 'stopped by the world' chip filters the table, disjoint from the
malformed, blocked and faulted counts by construction: it is an outcome, and
those counters never read the answer. countErrors now reads a precomputed
count the way countMalformed does, so an index stub never reads as clean.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: The episode view -- judge parse, the stop line, and the stub branch

**Files:**
- Modify: `trajectory_viewer.html` -- `renderEpisode`
- Test: `forge/tests/test_viewer.py`

**Interfaces:**
- Consumes: `fullLabel` (Task 2); `wasStopped`, `lastStop` (Task 5); `esc`, `parseRationale`, `backline`.
- Produces: nothing later tasks use.

- [ ] **Step 1: Write the failing tests**

Append to `forge/tests/test_viewer.py`:

```python
# -- the episode view: parse, stop line, and a stub for old campaigns ----------


def _episode_fn(viewer_html: str) -> str:
    source = viewer_source(viewer_html)
    fn = re.search(r"function renderEpisode\(content, s\) \{(.*?)\n\}", source, re.S)
    assert fn, "renderEpisode moved"
    return fn.group(1)


def test_the_run_bar_names_the_parse_only_when_the_run_carries_one(viewer_html):
    body = _episode_fn(viewer_html)
    assert "d.judge_parse ? `<span>judge parse <b>" in body


def test_a_stopped_episode_gets_one_credit_style_stop_line(viewer_html):
    body = _episode_fn(viewer_html)
    assert "if (wasStopped(d)) {" in body
    assert 'line.className = "credit";' in body
    assert "simulated seconds used" in body
    assert "no clock recorded for this run" in body
    assert 'line.title = String(st.reason || "");' in body


def test_an_index_stub_renders_a_summary_and_no_transcript(viewer_html):
    body = _episode_fn(viewer_html)
    stub = re.search(r"if \(d\.index_only\) \{(.*?)\n    return;\n  \}", body, re.S)
    assert stub, "renderEpisode needs an index_only branch that returns early"
    assert 'class="abstract"' in stub.group(1)
    assert "open files" in stub.group(1)
    assert body.index("if (d.index_only) {") < body.index('list.className = "transcript";')
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest forge/tests/test_viewer.py -k "run_bar_names or credit_style_stop or index_stub" -q`
Expected: 3 failed

- [ ] **Step 3: Name the parse in the run bar**

Edit `trajectory_viewer.html`. Old string (verbatim):

```
      <span>judge <b>${esc(judge)}</b></span>
      ${mal ? `<span class="warn-text">${esc(String(mal))} malformed</span>` : ""}
```

New string:

```
      <span>judge <b>${esc(judge)}</b></span>
      ${d.judge_parse ? `<span>judge parse <b>${esc(d.judge_parse)}</b></span>` : ""}
      ${mal ? `<span class="warn-text">${esc(String(mal))} malformed</span>` : ""}
```

- [ ] **Step 4: Add the stop line and the stub branch**

Edit `trajectory_viewer.html`. Old string (verbatim):

```
  if ((d.blocked_reasons || []).length)
    content.insertAdjacentHTML("beforeend",
      `<p class="note">Blocked: ${esc(d.blocked_reasons.join(" · "))}</p>`);
  content.insertAdjacentHTML("beforeend", `<p class="path">${esc(s.path)}</p>`);

  const types = [...new Set((d.events || []).map(e => e.type))];
```

New string:

```
  /* The world's own account of the ending, beside the verdict like the
     shaping signals: how much of the horizon was spent, and the state the
     environment stopped in. Absent when the agent answered. */
  if (wasStopped(d)) {
    const st = lastStop(d);
    const line = document.createElement("div");
    line.className = "credit";
    if (st) {
      line.title = String(st.reason || "");
      line.innerHTML = `<span class="lab">world stopped</span>
        <span><b>${esc(String(Math.round(st.time_passed)))}</b>${
          st.duration != null ? ` of <b>${esc(String(Math.round(st.duration)))}</b>` : ""}
          simulated seconds used</span>
        <span>${esc(String(st.env_state || ""))}</span>`;
    } else {
      line.innerHTML = `<span class="lab">world stopped</span>
        <span class="dim">no clock recorded for this run</span>`;
    }
    content.appendChild(line);
  }

  if ((d.blocked_reasons || []).length)
    content.insertAdjacentHTML("beforeend",
      `<p class="note">Blocked: ${esc(d.blocked_reasons.join(" · "))}</p>`);
  content.insertAdjacentHTML("beforeend", `<p class="path">${esc(s.path)}</p>`);

  /* An index stub: everything above came from the snapshot's index; the
     transcript is in the file on disk, which replaces this view when
     opened or dropped. */
  if (d.index_only) {
    content.insertAdjacentHTML("beforeend", `<div class="abstract">
      <h2>Transcript not in this copy</h2>
      <p>This page carries transcripts only for the
      <b>${esc(fullLabel || "current")}</b> campaign. Open
      <code>${esc(s.path)}</code> with <b>open files</b>, or drop it here,
      and it replaces this summary.</p></div>`);
    return;
  }

  const types = [...new Set((d.events || []).map(e => e.type))];
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest forge/tests/test_viewer.py -q`
Expected: all passed

- [ ] **Step 6: Commit**

```bash
git add trajectory_viewer.html forge/tests/test_viewer.py
git commit -m "Tell the episode view what parse read it, how it ended, and when to open the file

The run bar names the parse when the run carries one. A stopped episode gets
one line beside the verdict: how much of the horizon was spent and the state
the world stopped in, with the environment's own reason as the title. An
index stub renders everything the snapshot knows and then, in place of the
transcript, says which file to open and that it will replace this view.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: An evidence file's summary above its rows

**Files:**
- Modify: `trajectory_viewer.html` -- `renderSweeps`
- Test: `forge/tests/test_viewer.py`

**Interfaces:**
- Consumes: `s.data.summary` when present; `esc`.
- Produces: nothing later tasks use.

- [ ] **Step 1: Write the failing test**

Append to `forge/tests/test_viewer.py`:

```python
# -- an evidence file's summary, above its rows --------------------------------


def test_a_sweep_file_s_summary_renders_above_its_table(viewer_html):
    source = viewer_source(viewer_html)
    fn = re.search(r"function renderSweeps\(content\) \{(.*?)\n\}", source, re.S).group(1)
    assert "s.data.summary" in fn
    assert 'class="note summary"' in fn
    assert "slice(0, 160)" in fn
    assert fn.index('class="note summary"') < fn.index("const draw = () =>")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest forge/tests/test_viewer.py -k "summary_renders" -q`
Expected: 1 failed

- [ ] **Step 3: Render the summary**

Edit `trajectory_viewer.html`. Old string (verbatim):

```
  content.insertAdjacentHTML("beforeend",
    `<div class="panel-title">${esc(s.name)}
       <span class="sub">— ${esc(s.path)}</span></div>${
     note ? `<p class="note">${esc(note)}</p>` : ""}`);
  const twrap = document.createElement("div");
  twrap.className = "tabwrap";
  content.appendChild(twrap);
```

New string:

```
  content.insertAdjacentHTML("beforeend",
    `<div class="panel-title">${esc(s.name)}
       <span class="sub">— ${esc(s.path)}</span></div>${
     note ? `<p class="note">${esc(note)}</p>` : ""}`);
  /* A file's own summary -- the judge-parse file's transitions, a credit
     file's per-cell means -- is the claim; the rows are its evidence. One
     line per key, nothing file-specific. */
  const summary = !Array.isArray(s.data) && s.data.summary
    && typeof s.data.summary === "object" ? s.data.summary : null;
  if (summary)
    content.insertAdjacentHTML("beforeend", `<div class="note summary">${
      Object.entries(summary).map(([k, v]) => {
        const text = v !== null && typeof v === "object" ? JSON.stringify(v) : String(v);
        return `<div title="${esc(text)}"><b>${esc(k)}</b>: ${esc(text.slice(0, 160))}${
          text.length > 160 ? "…" : ""}</div>`;
      }).join("")}</div>`);
  const twrap = document.createElement("div");
  twrap.className = "tabwrap";
  content.appendChild(twrap);
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest forge/tests/test_viewer.py -q`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add trajectory_viewer.html forge/tests/test_viewer.py
git commit -m "Render an evidence file's summary above its rows

The judge-parse file's transitions and a credit file's per-cell means were
only inside the JSON. One key-value line each, above the table, nothing
file-specific.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: The Tasks section -- the pool, and each task's runs

**Files:**
- Modify: `trajectory_viewer.html` -- `SECTIONS`; `render()` dispatch; new `mdLite`, `renderTasks`, `renderTaskDetail` inserted before the `§3 Sweep evidence` banner
- Test: `forge/tests/test_viewer.py`

**Interfaces:**
- Consumes: `byKind("task")` (Task 2); every field of a task record (Task 1); `badge`, `verdictBadge(okr)`, `backline`, `openDetail`, `sessions`, `esc`, `$`.
- Produces: `mdLite(text) -> string`; `renderTasks(content)`; `renderTaskDetail(content, s)`.

- [ ] **Step 1: Write the failing tests**

Append to `forge/tests/test_viewer.py`:

```python
# -- the task pool: every task, and every run of it --------------------------


def test_tasks_is_the_second_section(viewer_html):
    source = viewer_source(viewer_html)
    secs = re.search(r"const SECTIONS = \[(.*?)\];", source, re.S).group(1)
    assert '["runs", "Runs"], ["tasks", "Tasks"]' in secs.replace("\n", "").replace("  ", " ")
    assert 'if (tab === "tasks") return renderTasks(content);' in source
    assert 'if (s.kind === "task") return renderTaskDetail(content, s);' in source


def test_the_tasks_table_names_what_a_task_is_and_who_it_may_use(viewer_html):
    source = viewer_source(viewer_html)
    fn = re.search(r"function renderTasks\(content\) \{(.*?)\n\}", source, re.S)
    assert fn, "renderTasks is missing"
    body = fn.group(1)
    for col in ("task", "substrate", "configuration", "target", "roster",
                "difficulty", "contract", "runs"):
        assert f"<th>{col}</th>" in body, col
    assert "family" in body and "verdictBadge(" not in body, (
        "the runs cell is a count, not a badge; a substrate is a word, not a colour")
    assert 'wireSearch(fbar, trs, "tasks")' in body, (
        "the tasks table shares the search helper rather than copying the filter block")
    assert "function wireSearch(fbar, trs, noun)" in source


def test_a_task_detail_renders_its_instruction_as_prose_and_its_runs(viewer_html):
    source = viewer_source(viewer_html)
    fn = re.search(r"function renderTaskDetail\(content, s\) \{(.*?)\n\}", source, re.S)
    assert fn, "renderTaskDetail is missing"
    body = fn.group(1)
    assert "mdLite(" in body
    assert "family match" in body
    assert "verdictBadge(" in body, "each run's verdict is a badge"
    assert "contract" in body and "d.contract_version" in body
    assert "sessions.findIndex(" in body, "a run row opens its breakdown ledger by path"


def test_md_lite_escapes_before_it_marks_up(viewer_html):
    source = viewer_source(viewer_html)
    fn = re.search(r"function mdLite\(text\) \{(.*?)\n\}", source, re.S)
    assert fn, "mdLite is missing"
    body = fn.group(1)
    assert body.index("esc(") < body.index("<h4>")
    assert 'class="mono"' in body and "<b>" in body and "<ul>" in body
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest forge/tests/test_viewer.py -k "second_section or tasks_table or task_detail or md_lite" -q`
Expected: 4 failed

- [ ] **Step 3: Add the section and the dispatch**

Edit `trajectory_viewer.html`. Old string (verbatim):

```
const SECTIONS = [["runs", "Runs"], ["breakdowns", "Shipped-task runs"],
                  ["sweeps", "Evidence files"]];
```

New string:

```
const SECTIONS = [["runs", "Runs"], ["tasks", "Tasks"],
                  ["breakdowns", "Shipped-task runs"], ["sweeps", "Evidence files"]];
```

Old string (verbatim):

```
    if (s.kind === "breakdown") return renderBreakdownDetail(content, s);
    return renderRaw(content, s, false);
  }
  if (tab === "runs") return renderRuns(content);
  if (tab === "breakdowns") return renderBreakdowns(content);
```

New string:

```
    if (s.kind === "breakdown") return renderBreakdownDetail(content, s);
    if (s.kind === "task") return renderTaskDetail(content, s);
    return renderRaw(content, s, false);
  }
  if (tab === "runs") return renderRuns(content);
  if (tab === "tasks") return renderTasks(content);
  if (tab === "breakdowns") return renderBreakdowns(content);
```

- [ ] **Step 4: Add `mdLite`, `renderTasks` and `renderTaskDetail`**

Edit `trajectory_viewer.html`. Old string (verbatim):

```
/* ================= §3 Sweep evidence ================= */
```

New string:

```
/* ================= §2b Tasks ================= */

/* The smallest markdown the instruction files use, as prose: headings,
   bullets, paragraphs, bold, and inline code as .mono. Escaped first, so
   nothing in a task's text can become markup. */
function mdLite(text) {
  const lines = esc(text).split("\n");
  const out = [];
  let list = null, para = [];
  const flush = () => {
    if (para.length) { out.push(`<p>${para.join(" ")}</p>`); para = []; }
    if (list) { out.push(`<ul>${list.join("")}</ul>`); list = null; }
  };
  const inline = s => s
    .replace(/`([^`]+)`/g, '<span class="mono">$1</span>')
    .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>");
  for (const raw of lines) {
    const line = raw.trimEnd();
    const h = line.match(/^(#{1,3})\s+(.*)$/);
    if (h) { flush(); out.push(h[1].length === 1 ? `<h4>${inline(h[2])}</h4>` : `<h5>${inline(h[2])}</h5>`); continue; }
    const b = line.match(/^-\s+(.*)$/);
    if (b) { if (para.length) { out.push(`<p>${para.join(" ")}</p>`); para = []; }
             (list = list || []).push(`<li>${inline(b[1])}</li>`); continue; }
    if (!line.trim()) { flush(); continue; }
    if (list) flush();
    para.push(inline(line));
  }
  flush();
  return out.join("\n");
}

function renderTasks(content) {
  const tasks = byKind("task");
  if (!tasks.length) {
    content.innerHTML = `<p class="lede">No tasks are loaded. The pool lives
      under <span class="mono">tasks/</span>; the snapshot carries one record
      per directory.</p>`;
    return;
  }
  const bySub = new Map();
  for (const s of tasks) {
    const k = s.data.substrate || "other";
    bySub.set(k, (bySub.get(k) || 0) + 1);
  }
  const NAMES = {appworld: "AppWorld", gaia2: "Gaia2", "parallel-scheduling": "parallel-scheduling"};
  content.insertAdjacentHTML("beforeend",
    `<h2 class="sec">Tasks</h2>
     <p class="lede"><b>${tasks.length}</b> task${tasks.length === 1 ? "" : "s"}: ${
       [...bySub].map(([k, n]) => `${n} ${NAMES[k] || k}`).join(", ")}. Each is a
     directory under <span class="mono">tasks/</span> a container runs; its Harbor
     runs under <span class="mono">jobs/</span> are linked beneath it.</p>
     <div class="panel-title">The pool
       <span class="sub">— click a row for its instruction and runs</span></div>`);

  const fbar = document.createElement("div");
  fbar.className = "filterline";
  fbar.innerHTML = `<span>restrict to
      <input type="search" placeholder="any text" aria-label="filter tasks"></span>
    <span class="count"></span>`;
  content.appendChild(fbar);

  const twrap = document.createElement("div");
  twrap.className = "tabwrap";
  twrap.innerHTML = `<table class="tab"><thead><tr>
      <th>task</th><th>substrate</th><th>configuration</th><th>target</th>
      <th>roster</th><th>difficulty</th><th>contract</th><th>runs</th>
    </tr></thead><tbody>${
    tasks.map(s => {
      const d = s.data;
      const exact = (d.runs || []).filter(r => r.match === "exact");
      const fam = (d.runs || []).filter(r => r.match === "family");
      const runs = exact.length
        ? `${exact.filter(r => r.success).length} of ${exact.length} passed${
            fam.length ? ` <span class="tag">+${fam.length} family</span>` : ""}`
        : fam.length ? `<span class="dim">—</span> <span class="tag">${fam.length} family</span>`
                     : `<span class="dim">—</span>`;
      const dash = v => v == null || v === "" ? `<span class="dim">—</span>` : esc(String(v));
      return `<tr class="click" data-i="${sessions.indexOf(s)}" tabindex="0"
        data-text="${esc(JSON.stringify([d.name, d.substrate, d.config, d.target,
                        d.roster, d.contract_version, d.description]).toLowerCase())}">
        <td title="${esc(d.description || "")}">${esc(d.name)}</td>
        <td>${dash(NAMES[d.substrate] || d.substrate)}</td>
        <td>${dash(d.config)}</td>
        <td>${dash(d.target)}</td>
        <td class="mono sm">${(d.roster || []).length ? (d.roster || []).map(esc).join(", ") : `<span class="dim">—</span>`}</td>
        <td>${dash(d.difficulty)}</td>
        <td class="mono sm">${dash(d.contract_version)}</td>
        <td>${runs}</td></tr>`;
    }).join("")}</tbody></table>`;
  const trs = [...twrap.querySelectorAll("tr.click")];
  trs.forEach(tr => tr.onclick = () => openDetail(Number(tr.dataset.i)));
  wireSearch(fbar, trs, "tasks");
  content.appendChild(twrap);
}

/* One search box over one table: rows carry data-text, the count line says
   how many survive. The runs and shipped-task tables predate this helper
   and keep their inline copies; new tables use it. */
function wireSearch(fbar, trs, noun) {
  const apply = () => {
    const q = $("input", fbar).value.toLowerCase();
    let shown = 0;
    for (const tr of trs) {
      const hit = !q || tr.dataset.text.includes(q);
      tr.style.display = hit ? "" : "none";
      shown += hit;
    }
    $(".count", fbar).textContent =
      shown === trs.length ? `all ${trs.length} ${noun}` : `${shown} of ${trs.length} ${noun}`;
  };
  fbar.addEventListener("input", apply);
  apply();
}

function renderTaskDetail(content, s) {
  const d = s.data;
  backline(content, "back to the tasks");
  const NAMES = {appworld: "AppWorld", gaia2: "Gaia2", "parallel-scheduling": "parallel-scheduling"};
  const dash = v => v == null || v === "" ? "—" : String(v);
  const bar = document.createElement("div");
  bar.className = "runbar";
  bar.innerHTML = `
    <h3><span>${esc(d.name)}</span>
      <span class="tag">${esc(NAMES[d.substrate] || d.substrate || "task")}</span></h3>
    <div class="facts">
      <span>configuration <b>${esc(dash(d.config))}</b></span>
      <span>target <b>${esc(dash(d.target))}</b></span>
      <span>difficulty <b>${esc(dash(d.difficulty))}</b></span>
      <span>category <b>${esc(dash(d.category))}</b></span>
      <span>contract <b class="mono">${esc(dash(d.contract_version))}</b></span>
      <span>verifier <b>${esc(dash(d.verifier_timeout_sec))}</b> s</span>
      <span>agent <b>${esc(dash(d.agent_timeout_sec))}</b> s</span>
      <span>${d.has_scenario ? "carries its scenario" : "no scenario file"}</span>
    </div>`;
  content.appendChild(bar);

  if (d.description)
    content.insertAdjacentHTML("beforeend", `<p class="lede">${esc(d.description)}</p>`);

  const panel = document.createElement("div");
  panel.className = "verdict-panel";
  panel.innerHTML = d.instruction
    ? `<div class="head">Instruction</div>${mdLite(d.instruction)}`
    : `<div class="head">Instruction</div><div>This task directory has no
       <span class="mono">instruction.md</span>.</div>`;
  content.appendChild(panel);

  const runs = d.runs || [];
  content.insertAdjacentHTML("beforeend",
    `<div class="panel-title">Harbor runs of this task
       <span class="sub">— ${runs.length ? "click a row for its verifier ledger" : "none under jobs/"}</span></div>`);
  if (runs.length) {
    const twrap = document.createElement("div");
    twrap.className = "tabwrap";
    twrap.innerHTML = `<table class="tab wrap"><thead><tr>
        <th>batch</th><th>when</th><th>verdict</th><th class="n">partial</th>
        <th class="n">deleg</th><th>answer</th>
      </tr></thead><tbody>${
      runs.map(r => `<tr class="click" tabindex="0" data-path="${esc(r.path)}">
        <td>${esc(r.batch)}</td>
        <td>${esc(dash(r.when))}</td>
        <td>${verdictBadge(!!r.success)}${
          r.match === "family" ? `<span class="tag">family match</span>` : ""}</td>
        <td class="n">${esc(dash(r.partial))}</td>
        <td class="n">${esc(dash(r.delegations))}</td>
        <td title="${esc(r.answer ?? "")}">${esc(String(r.answer ?? "").slice(0, 60))}</td></tr>`).join("")
      }</tbody></table>`;
    twrap.querySelectorAll("tr.click").forEach(tr => tr.onclick = () => {
      const i = sessions.findIndex(x => x.path === tr.dataset.path);
      if (i >= 0) openDetail(i);
    });
    content.appendChild(twrap);
    if (runs.some(r => r.match === "family"))
      content.insertAdjacentHTML("beforeend", `<p class="note">A run tagged
        <i>family match</i> named this task's stem without its numbered
        suffix in its path, so it is listed under every task of that family.</p>`);
  }

  content.insertAdjacentHTML("beforeend", `<p class="path">${esc(s.path)}</p>`);
  if ((d.files || []).length)
    content.insertAdjacentHTML("beforeend",
      `<details><summary>${d.files.length} file${d.files.length === 1 ? "" : "s"} in the task</summary>
       <pre>${esc(d.files.join("\n"))}</pre></details>`);
}

/* ================= §3 Sweep evidence ================= */
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest forge/tests/test_viewer.py -q`
Expected: all passed

- [ ] **Step 6: Commit**

```bash
git add trajectory_viewer.html forge/tests/test_viewer.py
git commit -m "Put the task pool on the page, each task with its Harbor runs beneath it

A Tasks section between Runs and Shipped-task runs: every directory under
tasks/ with its substrate, configuration, target, roster, difficulty and the
contract it shipped with, and a runs cell counting its exact-match Harbor
runs with family matches tagged. A task's detail renders its instruction as
prose -- headings, bullets, bold, inline code -- and a table of its runs, each
opening its verifier ledger. The contract cell is verbatim from the shipped
instruction, which is how the page shows that every Gaia2 task still says
objective-actions-v1 while the runtime is at v3.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 9: The producers refresh the page themselves

**Files:**
- Modify: `scripts/gaia2_campaign.py`, `scripts/gaia2_campaign_summary.py`, `scripts/gaia2_credit_probe.py`
- Test: `forge/tests/test_gaia2_campaign.py`

**Interfaces:**
- Consumes: `try_refresh(label=...)` from Task 1.
- Produces: nothing later tasks use.

- [ ] **Step 1: Write the failing tests**

Append to `forge/tests/test_gaia2_campaign.py`:

```python
# -- the producers refresh the viewer themselves -----------------------------

from pathlib import Path as _Path

_SCRIPTS = _Path(__file__).resolve().parents[2] / "scripts"


def test_the_campaign_refreshes_the_viewer_after_its_pool_and_never_on_dry_run():
    src = (_SCRIPTS / "gaia2_campaign.py").read_text()
    assert "from scripts.embed_logs import try_refresh" in src
    assert "try_refresh(args.label)" in src
    assert src.index("campaign complete") < src.index("try_refresh(args.label)")
    dry = src.index("if args.dry_run:")
    assert dry < src.index("try_refresh(args.label)")
    assert "return" in src[dry:src.index("def run_one")], "--dry-run must return early"


def test_the_summary_and_credit_probes_refresh_after_writing_their_evidence():
    for name in ("gaia2_campaign_summary.py", "gaia2_credit_probe.py"):
        src = (_SCRIPTS / name).read_text()
        assert "from scripts.embed_logs import try_refresh" in src, name
        assert "try_refresh(args.label)" in src, name
        assert src.index("dest.write_text(") < src.index("try_refresh(args.label)"), name
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest forge/tests/test_gaia2_campaign.py -k "refreshes" -q`
Expected: 2 failed

- [ ] **Step 3: The campaign runner**

Edit `scripts/gaia2_campaign.py`. Old string (verbatim):

```
from forge.gaia2.mine import admit
```

New string:

```
from forge.gaia2.mine import admit
from scripts.embed_logs import try_refresh
```

Old string (verbatim):

```
    print(f"campaign complete: {done} ran, {failed} errored")
```

New string:

```
    print(f"campaign complete: {done} ran, {failed} errored")
    # The page follows the results without anyone remembering embed_logs.
    # A refresh failure is reported, never raised: the rollouts are on disk.
    try_refresh(args.label)
```

- [ ] **Step 4: The summary probe**

Edit `scripts/gaia2_campaign_summary.py`. Old string (verbatim):

```
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
```

New string:

```
from pathlib import Path

from scripts.embed_logs import try_refresh

ROOT = Path(__file__).resolve().parents[1]
```

Old string (verbatim):

```
    dest.write_text(json.dumps(out, indent=1))
    print(f"wrote {dest.relative_to(ROOT)} ({len(rows)} cells)")
```

New string:

```
    dest.write_text(json.dumps(out, indent=1))
    print(f"wrote {dest.relative_to(ROOT)} ({len(rows)} cells)")
    try_refresh(args.label)
```

- [ ] **Step 5: The credit probe**

Edit `scripts/gaia2_credit_probe.py`. Old string (verbatim):

```
from forge.gaia2.runtime import zero_call_census
```

New string:

```
from forge.gaia2.runtime import zero_call_census
from scripts.embed_logs import try_refresh
```

Old string (verbatim):

```
    dest.write_text(json.dumps(out, indent=1))
    print(f"annotated {len(rows)} trajectories; wrote {dest.relative_to(ROOT)}")
```

New string:

```
    dest.write_text(json.dumps(out, indent=1))
    print(f"annotated {len(rows)} trajectories; wrote {dest.relative_to(ROOT)}")
    try_refresh(args.label)
```

- [ ] **Step 6: Run the tests, the suite and lint**

Run: `.venv/bin/python -m pytest forge/tests/test_gaia2_campaign.py -q && .venv/bin/python -m pytest -q && .venv/bin/python -m ruff check forge scripts`
Expected: all passed; `All checks passed!` (if ruff reports import ordering, run `.venv/bin/python -m ruff check --fix scripts` and re-run)

- [ ] **Step 7: Commit**

```bash
git add scripts/gaia2_campaign.py scripts/gaia2_campaign_summary.py scripts/gaia2_credit_probe.py forge/tests/test_gaia2_campaign.py
git commit -m "Let the producers refresh the viewer when they finish

The campaign after its pool -- unreachable from --dry-run, which returns
before it -- and the summary and credit probes after writing their evidence
file, each with its own label so the page's transcripts follow the campaign
just produced. try_refresh never raises: the results are already on disk and
the page is a view of them.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 10: The docs, the real snapshot, and the page in a browser

**Files:**
- Modify: `README.md` (the paragraph beginning "Each run writes a full trajectory to `output/rollouts/`"), `DESIGN.md` (the loading-model sentence)
- Modify: `trajectory_viewer.html` (its `#embedded-logs` block, by running the script -- never by hand)

**Interfaces:**
- Consumes: everything above.
- Produces: the shipped page.

- [ ] **Step 1: README**

Edit `README.md`. Old string (verbatim):

```
Each run writes a full trajectory to `output/rollouts/`, judged by Gaia2's own
write-action verifier (scripted by default; `--judge-model` runs the official
soft judge). Open `trajectory_viewer.html`, click **choose repository folder**
once, and select this repository; it then reads every current trajectory, sweep
file and sidecar breakdown directly without rebuilding the page.
```

New string:

```
Each run writes a full trajectory to `output/rollouts/`, judged by Gaia2's own
write-action verifier (scripted by default; `--judge-model` runs the official
soft judge). Open `trajectory_viewer.html`: it carries its own snapshot -- an
index of every episode ever run, with verdict, judge, parse, stop facts and
shaping signals; every task under `tasks/` with its Harbor runs linked; and
the full transcripts of the current campaign -- and the campaign, summary and
credit commands below refresh that snapshot themselves when they finish.
Older campaigns' transcripts open through the page's **open files** picker.
To refresh without a run: `uv run python -m scripts.embed_logs` (or
`--label v6` for a chosen campaign).
```

- [ ] **Step 2: DESIGN.md**

Edit `DESIGN.md`. Old string (verbatim):

```
surviving: **the loading model.** The page carries its own data. A JSON
snapshot of every log artifact sits in the `#embedded-logs` block, so opening
the file *is* the workflow.
```

New string:

```
surviving: **the loading model.** The page carries its own data. A JSON
snapshot sits in the `#embedded-logs` block -- an index of every episode ever
run, every task in the pool with its runs linked, every evidence file, and the
full transcripts of the current campaign -- so opening the file *is* the
workflow, and the producers refresh it when they finish.
```

- [ ] **Step 3: Rebuild the real snapshot**

Run: `.venv/bin/python -m scripts.embed_logs`
Expected: one line like `viewer: 613 episodes indexed across 6 campaigns; 10 tasks; transcripts for v6; 7.x MB`

Run: `ls -l trajectory_viewer.html | awk '{print $5}'`
Expected: a number under `8000000`

- [ ] **Step 4: Suite and lint**

Run: `.venv/bin/python -m pytest -q && .venv/bin/python -m ruff check forge scripts`
Expected: all passed (the contrast validator is untouched: no colour changed); `All checks passed!`

- [ ] **Step 5: Open the page from `file://` and check each item**

Run: `open trajectory_viewer.html`

Check, in order, and note anything that does not match:
1. The source line under the title names 613 episodes, 6 campaigns, 10 tasks, transcripts for v6.
2. The Runs view opens on **v6**; the campaign picker is first in the filter line and lists campaigns newest first, then "all campaigns".
3. The grid's note ends with the two-judge sentence and the stock-parse sentence naming `sweep/gaia2_v6_judge_parse.json`; no mark carries a parse tag.
4. Choosing **all campaigns** shows every label's marks; cells with several runs show their run labels.
5. The signal row has a **stopped by the world** chip; clicking it filters the table to rows whose `ended` cell reads `world stopped …`; clicking again clears it.
6. The runs table has an `ended` column between `issues` and `answer`.
7. Opening a v6 episode that stopped shows the stop line under the verdict panel with the seconds used, and the transcript below.
8. Choosing **all campaigns** and opening a `full`-campaign episode shows the verdict panel, signals, and the *Transcript not in this copy* block naming its path -- and no transcript.
9. Using **open files** to pick that episode's file from `output/rollouts/` replaces the stub: the transcript appears.
10. The **Tasks** tab is second in the nav and lists ten tasks: 6 AppWorld, 3 Gaia2, 1 parallel-scheduling. Every Gaia2 row's contract cell reads `objective-actions-v1`.
11. Opening `gaia2-star-docs-binf-scenario_universe_30_68r6vs` shows its roster (`Cabs`, `Calendar`, `Messages`), the contract in the facts line, the instruction as headed prose with code spans in monospace, and *none under jobs/* for its runs.
12. Opening `appworld-star-docs-binf-2a163ab_1` shows its runs table with rows from `final`, `final3`, `final4`, `verified`, `verified2` untagged and the `oracle-*`/`resweep` rows tagged *family match*; clicking a row opens that run's ledger; the same `oracle-1` run also appears under `_2` and `_3`.
13. The Evidence files view, on `gaia2_v6_judge_parse.json`, shows the `transitions` line above the table.
14. The theme toggle still works in both directions.

- [ ] **Step 6: Commit**

```bash
git add README.md DESIGN.md trajectory_viewer.html
git commit -m "Ship the viewer with every episode indexed, every task listed, and v6 in full

The snapshot now carries 613 episodes across six campaigns, the ten tasks
under tasks/ with their 22 Harbor runs linked, and the v6 transcripts, at a
page size under 8 MB. README and DESIGN.md describe the loading model as it
is: the page carries its own data, the producers refresh it, and older
campaigns' transcripts open through the picker.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Self-review

**Spec coverage.** §1 snapshot (index, tasks, files, linking rule, missing-file tasks) -> Task 1. §2 loading, stubs, task kind, source line -> Task 2. §3 picker -> Task 3. §4 parse stamp and judge sentence -> Task 4. §5 stop row, chip, episode line, stub branch -> Tasks 5 and 6. §6 evidence summary -> Task 7. §7 auto-refresh -> Task 9 (and `try_refresh` in Task 1). §8 Tasks section: `SECTIONS`, dispatch, `renderTasks` columns and runs cell, `renderTaskDetail` facts, `mdLite` prose, runs table with family tag opening ledgers by path, `.path` and files disclosure, the contract shown verbatim -> Task 8. Edge cases: unknown label (Task 1 test); two stop events (Task 1 `reversed`, Task 5 `lastStop`); no rollouts (Task 1 `newest_label([]) is None`, Task 2 artifacts source line); picked file replacing a stub (Task 2); one-label picker (Task 3 renders it regardless); family runs under each candidate and once in Shipped-task runs (Task 1 `link_runs`, Task 8 note; Shipped-task view untouched); task missing files (Task 1 test, Task 8 `dash` and the no-instruction panel); unlinkable run printed and left out (Task 1 test). Docs -> Task 10.

**Placeholders.** None: every step carries its code, its command and its expected outcome.

**Type consistency.** `snapshot(root, label)` / `refresh(label, root)` / `try_refresh(label, root)` match between Task 1's code and tests; `task_record(task_dir, root, runs)` and `link_runs(root, task_names)` match their tests and `snapshot()`'s calls; a run entry's keys (`path`, `batch`, `when`, `success`, `partial`, `delegations`, `answer`, `match`) are produced in Task 1 and read by name in Task 8; a task record's `name`, `path`, `substrate`, `config`, `target`, `description`, `difficulty`, `category`, `contract_version`, `verifier_timeout_sec`, `agent_timeout_sec`, `has_scenario`, `instruction`, `roster`, `files`, `runs` are produced in Task 1 and read by those names in Task 8; `fullLabel`/`campaignSel` are declared in Task 2 and read in Tasks 3 and 6; `wasStopped`/`lastStop` are defined in Task 5 and read in Task 6; `STOCK_PARSE`/`parseLabel` are defined and used only in Task 4; `detect` maps `forge-task` to `"task"` in Task 2 and `byKind("task")` is read in Task 8; `verdictBadge(!!r.success)` uses the one-argument form already used by `renderBreakdowns`.
