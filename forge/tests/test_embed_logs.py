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
            judge="gpt-5.6-sol", parse=None,
            scenario_id="scenario_universe_21_x", config="star-docs-binf"):
    d = {
        "kind": "gaia2-episode", "scenario_id": scenario_id,
        "config": config, "ability": "context-transfer",
        "label": label, "judge": judge, "started_at": started, "seconds": 61.0,
        "main_model": "m", "sub_model": "m", "delegations": 2,
        "specialist_turns": 5, "malformed": 0, "blocked": 0, "false_outages": 0,
        "answer": "(environment stopped)" if stopped else "booked it",
        "verdict": {"success": success, "rationale": "R" * 2000},
        "credit": {"partial_reward": 0.5, "coverage": 1.0, "fidelity": 0.0,
                   "gold_total": 7, "pivot": 3, "pivot_kind": "wrong-arguments"},
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
    (roll / "a__v6__1.json").write_text(json.dumps(episode(
        "v6", "2026-08-30 17:00:00", stopped=True,
        scenario_id="scenario_universe_30_x", config="star-docs-b4")))
    (roll / "b__v6__2.json").write_text(json.dumps(episode(
        "v6", "2026-08-30 18:00:00", success=True, parse="case-insensitive-v1",
        scenario_id="scenario_universe_30_x", config="star-docs-b4")))
    (roll / "c__full__1.json").write_text(json.dumps(episode("full", "2026-07-28 13:00:00")))
    (roll / "d__probe.json").write_text(json.dumps(episode(None, "2026-07-20 09:00:00")))
    (tmp_path / "sweep" / "gaia2_thing.json").write_text(json.dumps({"note": "n", "summary": {"k": 1}, "rows": [{"a": 1}]}))
    # Three tasks: two of one AppWorld family, one Gaia2.
    make_task(tmp_path, "appworld-star-docs-binf-2a163ab_1", APPWORLD_MD)
    make_task(tmp_path, "appworld-star-docs-binf-2a163ab_2", APPWORLD_MD)
    make_task(tmp_path, "gaia2-star-docs-b4-scenario_universe_30_x", GAIA2_MD)
    (tmp_path / "tasks" / "gaia2-star-docs-b4-scenario_universe_30_x" / "environment" / "scenario.json").write_text("{}")
    (tmp_path / "tasks" / "gaia2-star-docs-b4-scenario_universe_30_x" / "provenance.json").write_text(json.dumps({
        "scenario_id": "scenario_universe_30_x", "config": "star-docs-b4",
        "objective_action_contract": "objective-actions-v3",
        "judge_parse": "case-insensitive-v1", "runtime_digest": "abc123"}))
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
    assert r["credit"]["gold_total"] == 7, (
        "the viewer reads d.credit.gold_total unconditionally; a stub that "
        "drops it prints 'of undefined gold writes' (C2)")
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


def test_a_task_with_unparseable_toml_is_recorded_with_a_null_description(tmp_path):
    """`tomllib.TOMLDecodeError` is caught the same way a missing file is:
    the record still exists, with nulls where the broken file would have
    supplied fields (I7 -- this branch was untested)."""
    d = tmp_path / "tasks" / "gaia2-star-docs-binf-badtoml"
    d.mkdir(parents=True)
    (d / "task.toml").write_text("this is not [valid toml")
    r = task_record(d, tmp_path, [])
    assert r["description"] is None
    assert r["verifier_timeout_sec"] is None and r["agent_timeout_sec"] is None


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


def test_a_non_json_evidence_file_is_skipped_and_reported(tree, capsys):
    """The index loop and `link_runs` both catch `JSONDecodeError` and skip
    with a message; the `files` loop read `json.loads` bare (I6)."""
    (tree / "sweep" / "not_json.json").write_text("not json at all")
    snap = snapshot(root=tree)
    paths = {f["path"] for f in snap["files"]}
    assert "sweep/not_json.json" not in paths
    assert "skipping" in capsys.readouterr().out


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
    def strip(h):
        return re.sub(r'"generated":"[^"]*"', "", h)
    assert strip(again) == strip(html)


def test_try_refresh_reports_a_failure_and_never_raises(tmp_path, capsys):
    (tmp_path / "output" / "rollouts").mkdir(parents=True)
    try_refresh(root=tmp_path)
    assert "viewer refresh failed" in capsys.readouterr().out


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
