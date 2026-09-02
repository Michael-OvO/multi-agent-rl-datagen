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
    except Exception as e:  # noqa: BLE001
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
