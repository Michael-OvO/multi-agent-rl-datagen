"""Render admitted Gaia2 scenarios into Harbor tasks.

    python -m forge.gaia2.cli render \\
        --scenario gaia2_data/mini/scenario_universe_30_68r6vs.json --out tasks

One task per trainable ability (forge/abilities.py): the one-knob grid,
minus the OPEN control -- the control is the in-process ablation twin
(scripts/gaia2_cell_run.py --ability control), not a deliverable. Only
scenarios that are usable *and* seamful render, the same admission rule as
`forge/gaia2/render.py`: a task without a proven information seam does not
force a fact through a conversation, so it prices nothing.
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys
from pathlib import Path

from forge.abilities import Ability, config_for
from forge.gaia2.harbor import write_task
from forge.gaia2.mine import admit


def cmd_render(args: argparse.Namespace) -> None:
    if args.economy_target is not None and args.economy_target < 1:
        raise SystemExit("--economy-target must be positive")
    scenario_path = Path(args.scenario)
    scenario = json.loads(scenario_path.read_text())
    span = admit(scenario)
    if not (span.usable and span.seamful):
        raise SystemExit(
            f"{span.scenario_id}: usable={span.usable} seamful={span.seamful} -- "
            "only admitted scenarios render; see sweep/gaia2_*_admission.json")
    if span.roster_blind:
        facts = ", ".join(
            f"{f.arg} needs {f.leaf!r} (only in {'/'.join(f.sources)})"
            for f in span.roster_blind[:3])
        raise SystemExit(
            f"{span.scenario_id}: roster-blind, will not render -- the gold "
            f"writes consume facts no seat can read: {facts}. Every episode "
            f"on this partition is a guaranteed failure.")

    print(f"{span.scenario_id}: roster {span.roster}")
    target = (
        span.delegation_target
        if args.economy_target is None
        else args.economy_target
    )
    for ability in (Ability.DISCOVERY, Ability.CONTEXT_TRANSFER,
                    Ability.DELEGATION_ECONOMY):
        c = config_for(ability, span.roster, budget_target=target)
        # One token per task. It gates the sidecar's /state endpoint and
        # lives only in tests/, which Harbor uploads after the agent phase.
        d = write_task(scenario_path, span.scenario_id, c, args.out,
                       token=secrets.token_hex(16))
        print(f"  {d.name}   ({ability.value})")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="forge.gaia2.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)

    render = sub.add_parser("render", help="render one admitted scenario "
                            "into its three ability tasks")
    render.add_argument("--scenario", required=True,
                        help="path to a fetched scenario JSON")
    render.add_argument("--out", type=Path, default=Path("tasks"))
    render.add_argument(
        "--economy-target",
        type=int,
        default=None,
        help="override the task-derived soft bN target for the economy task",
    )
    render.set_defaults(fn=cmd_render)

    args = parser.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main(sys.argv[1:])
