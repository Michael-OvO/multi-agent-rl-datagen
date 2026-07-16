"""Measure whether each constraint knob actually moves the score.

This is the anti-toy gate. A knob that does not change the outcome against the
`open` control is decoration, and decoration is exactly what this design is
supposed to exclude. Every knob in `partition.py` has to earn its place here or
be deleted.

Reward is AppWorld's `evaluate()` -- programmatic, no LLM, and it checks side
effects as well as completion. We do not compute it, we read it.

Usage:
    python -m scripts.appworld_knob_sweep --tasks 3 --out sweep/appworld.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path

from forge.appworld.partition import Constraints, Topology, Visibility, control_for
from forge.appworld.runtime import RunLog, run_main, run_specialist


_ACTION_ANSWERS = ("completed", "complete", "done", "", "(out of steps)", "(error)")


def _is_action_answer(answer: str) -> bool:
    """True when the Main reported an action rather than a value."""
    a = str(answer).strip().lower()
    return a in _ACTION_ANSWERS or a.startswith(("liked ", "unable", "no venmo"))


def _configs(roster: tuple[str, ...]) -> list[Constraints]:
    """The control plus the configurations whose effect we are measuring."""
    return [
        control_for(roster),
        Constraints(roster=roster, topology=Topology.STAR, visibility=Visibility.DOCS),
        Constraints(roster=roster, topology=Topology.STAR, visibility=Visibility.NAMES),
        Constraints(roster=roster, topology=Topology.CHAIN, visibility=Visibility.NAMES),
    ]


def _run_open_control(client, world, task: str, roster, log: RunLog, model: str) -> str:
    """Control condition: no partition. One agent holds every app.

    Implemented as a single 'specialist' whose app set is the whole roster, so
    the control differs from the partitioned runs in exactly one thing -- the
    constraint -- and nothing else.

    The roster is passed as a *tuple*, not as a pre-joined display string. It
    used to be `"`, `apis.".join(roster)`, which made the prompt's prose read
    correctly and its workflow emit
    `show_api_descriptions(app_name='phone`, `apis.venmo')` -- a call that cannot
    run. The control therefore never saw a catalog and reached 1.000 by guessing
    API names. Formatting for display and naming what an agent may touch are two
    different jobs; conflating them also meant the sandbox read the whole joined
    string as one app name and refused the control every API it had.
    """
    return run_specialist(client, world, tuple(roster), task, log, model=model,
                          max_turns=20)


def run_one(client, task_id: str, roster: tuple[str, ...], c: Constraints,
            main_model: str, sub_model: str) -> dict:
    from appworld import AppWorld

    log = RunLog()
    started = time.time()
    with AppWorld(task_id=task_id, experiment_name=f"knob_{c.label}",
                  ground_truth_mode="full") as w:
        task = w.task.instruction
        try:
            if c.main_has_apis:
                answer = _run_open_control(client, w, task, roster, log, main_model)
            else:
                answer = run_main(client, w, task, c, log, model=main_model,
                                  sub_model=sub_model)
            error = None
        except Exception as e:  # a crashed rollout is a data point, not a stop
            answer, error = "(error)", f"{type(e).__name__}: {e}"[:200]
            # A rollout that never ran is not a rollout. Without this, a
            # misconfigured call (e.g. a model rejecting temperature=0) 400s on
            # every turn, gets swallowed here, and still reports a plausible
            # partial score -- which is indistinguishable from a real result.
            print(f"  !! {task_id} {c.label}: {error}", flush=True)

        # AppWorld expects the task's answer type. Action tasks ("like all the
        # transactions") return None in their GT; submitting prose fails the
        # `assert answers match` requirement and caps them at 5/6 = 0.833.
        # Measured: same work, prose -> 0.833; None -> 1.000, success=True.
        submitted = None if _is_action_answer(answer) else answer
        w.execute("apis.supervisor.complete_task(answer=%r, status='success')"
                  % (submitted,) if submitted is not None
                  else "apis.supervisor.complete_task(answer=None, status='success')")
        ev = w.evaluate().to_dict()

    passes, failures = len(ev.get("passes", [])), len(ev.get("failures", []))
    total = passes + failures
    return {
        "task_id": task_id,
        "config": c.label,
        "main_model": main_model,
        "sub_model": sub_model,
        "roster": list(roster),
        "success": bool(ev.get("success")),
        # Partial credit from the oracle's own unit tests. Not our invention:
        # AppWorld reports per-requirement pass/fail and we count them.
        "partial": round(passes / total, 3) if total else 0.0,
        "passes": passes,
        "failures": failures,
        "delegations": log.delegations,
        "specialist_turns": log.specialist_turns,
        "refusals": log.refusals,
        "answer": str(answer)[:160],
        "error": error,
        # A row with no turns did no work: the agent never executed anything, so
        # whatever score it carries describes the untouched world, not a policy.
        # Aggregation must drop these, not average them in.
        "ran": log.specialist_turns > 0,
        "seconds": round(time.time() - started, 1),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", type=int, default=3, help="how many tasks to sweep")
    ap.add_argument("--span", type=Path, default=Path("sweep/appworld_span.json"))
    ap.add_argument("--out", type=Path, default=Path("sweep/appworld_knobs.json"))
    ap.add_argument("--main-model", default="gpt-5.6-sol",
                    help="the model under test; must be strong enough that the "
                         "OPEN control can succeed, or knob effects are unmeasurable")
    ap.add_argument("--sub-model", default="gpt-4.1",
                    help="specialists: narrow, mechanical work; a cheap model is fine")
    args = ap.parse_args()

    from scripts._env import ensure_appworld_root, require_api_key
    ensure_appworld_root()
    require_api_key()

    from openai import OpenAI

    client = OpenAI()

    spans = json.loads(args.span.read_text())
    usable = [s for s in spans if len(s["roster"]) >= 2][: args.tasks]
    if not usable:
        raise SystemExit(f"no usable tasks in {args.span}")

    rows: list[dict] = []
    for s in usable:
        roster = tuple(s["roster"])
        for c in _configs(roster):
            row = run_one(client, s["task_id"], roster, c,
                          args.main_model, args.sub_model)
            rows.append(row)
            print(f"{row['task_id']:12} {row['config']:18} "
                  f"success={str(row['success']):5} partial={row['partial']:.2f} "
                  f"deleg={row['delegations']} {row['seconds']}s"
                  + (f"  ERR {row['error'][:40]}" if row["error"] else ""))
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(rows, indent=1))

    print(f"\nwrote {len(rows)} rows to {args.out}")


if __name__ == "__main__":
    main()
