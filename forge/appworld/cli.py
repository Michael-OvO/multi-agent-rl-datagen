"""The task-forging pipeline for the AppWorld dimension.

    python -m forge.appworld.cli measure --out sweep/appworld_span.json
    python -m forge.appworld.cli render --n 3 --out tasks
    python -m forge.appworld.cli judge --sweep sweep/appworld_knobs_v5.json

`measure` reads every ground-truth-bearing AppWorld task and records the roster
each one actually needs. `render` turns selected tasks + constraint
configurations into Harbor task directories. `judge` reads a finished sweep and
reports which rendered cells are usable RL data at all -- the rule in
`validity.py`, which is worth nothing unless it is runnable.

The pipeline never invents a task, a roster, a reward, or a verifier. It selects,
constrains, and packages.
"""

from __future__ import annotations

import argparse
import json
import secrets
from pathlib import Path

from forge.appworld.harbor import write_task
from forge.appworld.partition import Constraints, Topology, Visibility
from forge.appworld.reference import REFERENCE_PATHS
from forge.appworld.select import MIN_ROSTER, span_of, usable
from forge.appworld.validity import judge_rows, yield_by_config


def cmd_measure(args: argparse.Namespace) -> None:
    from appworld import AppWorld, load_task_ids

    spans = []
    for split in ("train", "dev"):  # only these carry ground truth
        for task_id in load_task_ids(split):
            with AppWorld(task_id=task_id, experiment_name="measure",
                          ground_truth_mode="full") as w:
                spans.append(span_of(task_id, split, w.task.instruction,
                                     w.task.ground_truth.solution_code))

    rows = [{"task_id": s.task_id, "split": s.split, "instruction": s.instruction,
             "roster": list(s.roster)} for s in spans]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rows, indent=1))

    keep = usable(spans)
    print(f"measured {len(spans)} tasks; {len(keep)} usable (roster >= {MIN_ROSTER})")
    print(f"dropped {len(spans) - len(keep)} single-app tasks -- not padded with "
          "a decorative specialist")
    print(f"wrote {args.out}")


#: The configurations we ship. A knob that has not been shown to move the score
#: against the OPEN control is decoration; a knob that moves it by breaking the
#: task is worse. See scripts/appworld_knob_sweep.py for the evidence.
#:
#: CHAIN is NOT shipped. Measured -- sweep/appworld_knobs_v5.json: 0.333/0.333/
#: 0.167, deleg 12/12/9. Two hit `max_steps` (12) and answered `(out of steps)`;
#: on the third the Main spent 9 and then reported the missing handoff in as many
#: words, which is the better evidence. The Main can reach only `roster[0]`, and
#: the specialist->specialist handoff that CHAIN's whole point depends on is
#: defined in `Constraints.allowed_targets` and called by nothing. The topology is
#: unimplemented, so the task is unsolvable, so its difficulty signal is fake.
#: It ships when the handoff exists and is measured, not before.
SHIPPED_CONFIGS = (
    (Topology.STAR, Visibility.DOCS, None),
    (Topology.STAR, Visibility.NAMES, None),
)


def cmd_render(args: argparse.Namespace) -> None:
    rows = json.loads(args.span.read_text())
    candidates = [r for r in rows if len(r["roster"]) >= MIN_ROSTER]
    # Tasks with a recorded reference orchestration come first: they are the
    # only ones that can ship a demonstrated solution, and a task nobody has
    # solved is not a deliverable. Stable, so span order holds within each group.
    candidates.sort(key=lambda r: r["task_id"] not in REFERENCE_PATHS)
    keep = candidates[: args.n]
    if not keep:
        raise SystemExit(f"no usable tasks in {args.span}; run `measure` first")

    written, solvable = [], 0
    for row in keep:
        roster = tuple(row["roster"])
        reference = REFERENCE_PATHS.get(row["task_id"])
        for topology, visibility, budget in SHIPPED_CONFIGS:
            c = Constraints(roster=roster, topology=topology,
                            visibility=visibility, delegation_budget=budget)
            # One token per task. It gates the sidecar's /state endpoint and
            # lives only in tests/, which Harbor uploads after the agent phase.
            d = write_task(row["task_id"], row["instruction"], c, args.out,
                           token=secrets.token_hex(16), reference=reference)
            written.append(d)
            solvable += reference is not None
            print(f"  {d.name}{'' if reference else '   (no solution: no reference)'}")

    print(f"\nwrote {len(written)} Harbor tasks to {args.out}")
    print(f"{solvable} ship a reference solution; {len(written) - solvable} do not")


def _floor_from(path: Path) -> float:
    """The do-nothing floor, read rather than assumed.

    Asserted to be one number across tasks: a floor that varies per task is not
    a floor, and reading a knob against the wrong one is how 0.333 got published
    as difficulty.
    """
    rows = json.loads(path.read_text())
    floors = {r["partial"] for r in rows}
    if len(floors) != 1:
        raise SystemExit(f"{path}: the do-nothing floor is not a single number: {floors}")
    return floors.pop()


def cmd_judge(args: argparse.Namespace) -> None:
    floor = args.floor if args.floor is not None else _floor_from(args.donothing)
    rows = json.loads(args.sweep.read_text())
    judgements = judge_rows(rows, floor)

    print(f"floor={floor}  ({len(judgements)} constrained cells)\n")
    print(f"{'config':<18}{'task':<12}{'score':>7}{'control':>9}  verdict")
    print("-" * 66)
    for j in sorted(judgements, key=lambda j: (j.config, j.task_id)):
        print(
            f"{j.config:<18}{j.task_id:<12}{j.score:>7.3f}{j.control:>9.3f}"
            f"  {j.verdict.value}"
        )

    print(f"\n{'config':<18}{'usable':>8}{'rate':>8}{'seeds':>7}  ")
    print("-" * 66)
    for config, y in sorted(yield_by_config(judgements).items()):
        note = "yield" if y.measured else f"observed only ({y.seeds} seed/cell)"
        unmeasurable = f"  +{y.unmeasurable} unmeasurable" if y.unmeasurable else ""
        print(
            f"{config:<18}{f'{y.valid}/{y.total}':>8}{y.rate:>8.0%}{y.seeds:>7}"
            f"  {note}{unmeasurable}"
        )


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="forge.appworld")
    sub = p.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("measure", help="record each task's task-determined roster")
    m.add_argument("--out", type=Path, default=Path("sweep/appworld_span.json"))
    m.set_defaults(func=cmd_measure)

    r = sub.add_parser("render", help="render Harbor tasks")
    r.add_argument("--n", type=int, default=3, help="how many AppWorld tasks")
    r.add_argument("--span", type=Path, default=Path("sweep/appworld_span.json"))
    r.add_argument("--out", type=Path, default=Path("tasks"))
    r.set_defaults(func=cmd_render)

    j = sub.add_parser("judge", help="which swept cells are usable RL data")
    j.add_argument("--sweep", type=Path, default=Path("sweep/appworld_knobs_v5.json"))
    j.add_argument(
        "--donothing",
        type=Path,
        default=Path("sweep/appworld_donothing.json"),
        help="measured floor; --floor overrides",
    )
    j.add_argument("--floor", type=float, default=None)
    j.set_defaults(func=cmd_judge)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
