"""Merge per-replicate sweep files into the one file the docs and tests read.

    python -m scripts.merge_seeds sweep/appworld_knobs_v5.json sweep/_seed_*.json \
        --out sweep/appworld_seeds.json

`appworld_knob_sweep.py` writes one file per run because AppWorld's experiment
directories collide if two runs share a name. The validity rule wants them
together: a cell's verdict is a property of the spread across its replicates, so
a file holding one replicate of each cell can only ever report an observation
(`validity.SEEDS_FOR_YIELD`).

Refuses rather than guesses, on the theory that a merge which quietly drops or
double-counts a replicate produces a yield nobody can reproduce:

  * every row must carry a `seed`, or the merge cannot tell replicates apart;
  * no (task, config, seed) may appear twice -- two files claiming to be the
    same replicate means one of them is a re-run nobody labelled;
  * every cell must end up with the same number of replicates, or the weakest
    cell governs the yield while the mean is computed off the strongest.

The third is a warning rather than an error: an interrupted sweep is a real
thing to want to look at, and `Yield.seeds` already reports the weakest cell.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def merge(paths: list[Path]) -> list[dict]:
    rows: list[dict] = []
    for p in paths:
        loaded = json.loads(p.read_text())
        for r in loaded:
            if "seed" not in r:
                raise SystemExit(
                    f"{p}: a row has no `seed`, so replicates cannot be told apart. "
                    f"Re-run with --seed, or backfill the label if you know it."
                )
        rows.extend(loaded)

    seen = Counter((r["task_id"], r["config"], r["seed"]) for r in rows)
    dupes = [k for k, n in seen.items() if n > 1]
    if dupes:
        raise SystemExit(
            f"{len(dupes)} (task, config, seed) triples appear more than once, "
            f"e.g. {dupes[0]}. Two files claim the same replicate; one is an "
            f"unlabelled re-run and merging them would double-count it."
        )
    return sorted(rows, key=lambda r: (r["task_id"], r["config"], r["seed"]))


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="scripts.merge_seeds")
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, default=Path("sweep/appworld_seeds.json"))
    args = ap.parse_args(argv)

    rows = merge(args.files)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rows, indent=1) + "\n")

    per_cell = Counter((r["task_id"], r["config"]) for r in rows)
    seeds = sorted({r["seed"] for r in rows})
    print(f"wrote {args.out}: {len(rows)} rows, seeds {seeds}")
    print(f"{len(per_cell)} cells, {min(per_cell.values())}-{max(per_cell.values())} "
          f"replicates each")
    if len(set(per_cell.values())) > 1:
        thin = [c for c, n in per_cell.items() if n == min(per_cell.values())]
        print(f"  WARNING: uneven replicates; the weakest cell ({thin[0]}) governs "
              f"the yield. See validity.Yield.seeds.")


if __name__ == "__main__":
    main()
