"""Render the Gaia2 cell grid: what would we run, priced per ability? (no LLM)

Takes the admission measurement's seamful scenarios and renders the full
cell grid -- shared control plus one cell per ability, per scenario -- with
roster, seam edges and structural difficulty stamped on every row. This is
the work-order list for the future ARE runtime, and the denominator of the
first Gaia2 yield.

    uv run python -m scripts.gaia2_render_probe

Reads gaia2_data/mini/*.json, writes sweep/gaia2_cells.json. Deterministic.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from forge.gaia2.render import render_cells


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default="mini")
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--economy-target", type=int, default=None)
    target.add_argument("--economy-target-offset", type=int, default=0)
    args = parser.parse_args()
    if args.economy_target is not None and args.economy_target < 1:
        parser.error("--economy-target must be positive")
    in_dir = Path(f"gaia2_data/{args.split}")
    # `mini` keeps its original filename; other splits are suffixed.
    out = Path(
        "sweep/gaia2_cells.json"
        if args.split == "mini"
        else f"sweep/gaia2_cells_{args.split}.json"
    )

    paths = sorted(in_dir.glob("*.json"))
    if not paths:
        raise SystemExit(
            f"no scenarios in {in_dir}. Run:\n"
            f"  uv run --with pandas --with pyarrow python -m scripts.gaia2_fetch"
            f" --split {args.split}"
        )

    scenarios = [json.loads(p.read_text()) for p in paths]
    cells = render_cells(
        scenarios,
        economy_target=args.economy_target,
        economy_target_offset=args.economy_target_offset,
    )

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps([c.as_row() for c in cells], indent=1))

    n_scenarios = len({c.scenario_id for c in cells})
    print(f"scenarios rendered: {n_scenarios} of {len(scenarios)}")
    print(f"cells: {len(cells)}")
    by_ability = Counter(
        c.ability.value if c.ability else "control" for c in cells
    )
    for name, count in sorted(by_ability.items()):
        print(f"  {name}: {count}")

    rostered = Counter(len(c.roster) for c in cells if c.ability is None)
    print("roster sizes (per scenario):", dict(sorted(rostered.items())))
    writes = [c.writes for c in cells if c.ability is None]
    depths = [c.depth for c in cells if c.ability is None]
    widths = [c.width for c in cells if c.ability is None]
    print(
        f"structure: writes {min(writes)}-{max(writes)}, "
        f"depth {min(depths)}-{max(depths)}, width {min(widths)}-{max(widths)}"
    )
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
