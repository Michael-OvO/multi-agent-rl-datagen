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
