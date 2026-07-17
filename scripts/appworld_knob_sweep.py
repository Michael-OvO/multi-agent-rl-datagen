"""Measure whether each constraint knob actually moves the score.

This is the anti-toy gate. A knob that does not change the outcome against the
`open` control is decoration, and decoration is exactly what this design is
supposed to exclude. Every knob in `partition.py` has to earn its place here or
be deleted.

Reward is AppWorld's `evaluate()` -- programmatic, no LLM, and it checks side
effects as well as completion. We do not compute it, we read it.

Usage:
    python -m scripts.appworld_knob_sweep --tasks 3 --out sweep/appworld_knobs_v5.json
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from forge.appworld.partition import Constraints, Topology, Visibility, control_for
from forge.appworld.reference import REFERENCE_PATHS
from forge.appworld.runtime import (
    NO_ANSWER,
    OUT_OF_STEPS,
    RunLog,
    run_main,
    run_specialist,
)
from forge.appworld.seams import information_seam_task_ids
from forge.appworld.select import MIN_ROSTER

#: The protocol words the instruction asks for. Identical to the shipped
#: sidecar's `container/server.py::_as_answer`, deliberately: a sweep that
#: converts answers the container would not is a sweep measuring a different
#: task than the one that ships. Pinned by forge/tests/test_knob_sweep.py.
_ACTION_ANSWERS = ("completed", "complete", "done", "")

#: The harness's own markers for "the agent never answered". They submit None
#: for the same reason the do-nothing probe does -- a dead run's score should
#: come from the world's state, not from a penalty for a string the agent never
#: wrote. (Submitting these as prose fails `assert answers match` and drops a
#: dead run to 1/6 = 0.167, the pre-fix floor, which no probe measures.)
#:
#: Imported from `runtime`, not re-typed. As literals this list was missing
#: `NO_ANSWER`, which only the OPEN control can emit -- it answers through
#: `run_specialist` while every partitioned arm goes through `run_main` -- so
#: the single row that can depress the ceiling every knob is read against was
#: the one row nothing covered. `_ERROR` stays local: the sweep raises it, not
#: the runtime. Pinned by forge/tests/test_knob_sweep.py.
_ERROR = "(error)"
_HARNESS_SENTINELS = (OUT_OF_STEPS, NO_ANSWER, _ERROR)


def _is_action_answer(answer: str) -> bool:
    """True when the Main reported an action rather than a value.

    This used to also match `("liked ", "unable", "no venmo")` -- phrasings read
    off the one shipped task family. Measured: those prefixes fired on **every
    open-control row and on nothing else**, because the control is the only arm
    never told the answer protocol. They silently converted its prose to None
    and lifted it from 0.833 to 1.000 -- and the control is the ceiling every
    knob is read against. A heuristic that rescues only the reference point is
    not a formatting convenience. The control is told the protocol now
    (`_run_open_control`), so it can say `completed` like every other arm.
    """
    a = str(answer).strip().lower()
    return a in _ACTION_ANSWERS or a in _HARNESS_SENTINELS


def _configs(roster: tuple[str, ...], only: set[str] | None = None) -> list[Constraints]:
    """The control plus the configurations whose effect we are measuring.

    `only` selects by label. The control is always included: a constrained score
    with no ceiling to be read against is not a measurement (validity.py raises
    on exactly that), so filtering it out would produce a file the judge refuses.
    """
    all_of = [
        control_for(roster),
        Constraints(roster=roster, topology=Topology.STAR, visibility=Visibility.DOCS),
        Constraints(roster=roster, topology=Topology.STAR, visibility=Visibility.NAMES),
        Constraints(roster=roster, topology=Topology.CHAIN, visibility=Visibility.NAMES),
    ]
    if not only:
        return all_of
    keep = [c for c in all_of if c.label in only or c.main_has_apis]
    unknown = only - {c.label for c in all_of}
    if unknown:
        raise SystemExit(
            f"unknown config(s) {sorted(unknown)}; "
            f"available: {sorted(c.label for c in all_of)}"
        )
    return keep


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
    # The control's FINAL line is submitted to AppWorld as the task's answer, so
    # it needs the same answer protocol `run_main` gives the partitioned Main.
    # Without it the control answers prose, `assert answers match` fails, and the
    # control alone is capped at 0.833 -- which is how a string heuristic came to
    # be holding up the ceiling every other number is read against.
    brief = (
        f"{task}\n\n"
        "Your FINAL line is submitted as this task's answer. If the task asked "
        "you to DO something rather than to report a value, your FINAL line must "
        "be exactly `completed`. Otherwise it must be the value asked for and "
        "nothing else."
    )
    return run_specialist(client, world, tuple(roster), brief, log, model=model,
                          max_turns=20)


def run_one(client, task_id: str, roster: tuple[str, ...], c: Constraints,
            main_model: str, sub_model: str, seed: int = 1) -> dict:
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
            answer, error = _ERROR, f"{type(e).__name__}: {e}"[:200]
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
        # `%r` of None is already "None", so the else-branch this used to carry
        # produced a byte-identical string and never ran. It also parsed only by
        # precedence accident: `%` binds tighter than the conditional, so it read
        # as though the format applied to the whole ternary.
        w.execute("apis.supervisor.complete_task(answer=%r, status='success')"
                  % (submitted,))
        ev = w.evaluate().to_dict()

    failed = [str(f) for f in ev.get("failures", [])]
    passes, failures = len(ev.get("passes", [])), len(failed)
    total = passes + failures
    return {
        "task_id": task_id,
        "config": c.label,
        "seed": seed,
        "main_model": main_model,
        "sub_model": sub_model,
        "roster": list(roster),
        "success": bool(ev.get("success")),
        # Partial credit from the oracle's own unit tests. Not our invention:
        # AppWorld reports per-requirement pass/fail and we count them.
        "partial": round(passes / total, 3) if total else 0.0,
        "passes": passes,
        "failures": failures,
        # The names, not just the count -- the container has recorded these since
        # WRITEUP.md section 7.4 ("log the names, not the counts") and the sweep
        # did not, which is why the answer-protocol contamination went unseen:
        # `partial=0.167` says one of six passed and cannot say that the one was
        # `assert answers match`.
        "failed": failed,
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
    ap.add_argument(
        "--configs", nargs="*", default=None, metavar="LABEL",
        help="only these configs (the control is always included). Use to spend "
             "replicates on what ships: `chain-names-binf` is unimplemented and "
             "known degenerate, and re-confirming that costs the most wall clock "
             "of any cell in the sweep.")
    ap.add_argument(
        "--seed", type=int, default=1,
        help="replicate label, recorded on each row. There is no RNG to seed: the "
             "variance under test is the Main's own sampling (gpt-5.x rejects "
             "temperature=0 and runs at the default; specialists run at 0). "
             "Validity is a property of the distribution over replicates, so one "
             "of these measures nothing -- see forge/appworld/validity.py.")
    ap.add_argument("--span", type=Path, default=Path("sweep/appworld_span.json"))
    ap.add_argument("--seams", type=Path, default=Path("sweep/appworld_seams.json"))
    ap.add_argument("--out", type=Path, default=Path("sweep/appworld_knobs_v5.json"),
                    help="the file the docs and tests read; a new name here is a "
                         "sweep nothing checks")
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
    seam_rows = json.loads(args.seams.read_text())
    try:
        seam_task_ids = information_seam_task_ids(spans, seam_rows)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    # Same selection the renderer uses, or the sweep measures tasks that do not
    # ship: the roster and information-seam gates, then reference-bearing tasks
    # first (cli.cmd_render uses the same measurements and ordering).
    candidates = [
        span
        for span in spans
        if len(span["roster"]) >= MIN_ROSTER
        and span["task_id"] in seam_task_ids
    ]
    candidates.sort(key=lambda s: s["task_id"] not in REFERENCE_PATHS)
    usable = candidates[: args.tasks]
    if not usable:
        raise SystemExit(f"no usable tasks in {args.span}")

    rows: list[dict] = []
    for s in usable:
        roster = tuple(s["roster"])
        for c in _configs(roster, only=set(args.configs) if args.configs else None):
            row = run_one(client, s["task_id"], roster, c,
                          args.main_model, args.sub_model, seed=args.seed)
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
