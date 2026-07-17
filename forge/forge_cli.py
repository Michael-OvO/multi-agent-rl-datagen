"""forge — generate verifiable multi-agent RL tasks in Harbor format.

**This is v1, and it is kept as the retrospective, not as the method.** It
designs the world *and* the judge, which is what WRITEUP.md section 1 is about:
`theory-of-mind` scored 1.0 on 12 of 12 runs with zero gradient while every gate
below stayed green. The current forge is `forge/appworld/` -- it designs
constraints and inherits AppWorld's judge. Read WRITEUP.md section 1 before
taking anything here as a recommendation.

Every generated instance passes the CLEAN/VALID selfcheck battery before it is
written; failures are logged and skipped -- and that sentence is exactly the
problem: the battery was green for a dimension worth nothing. Usage:

    python -m forge.forge_cli gen --dim parallel-scheduling \
        --seed 0 --n 100 --difficulty medium --out tasks/
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from forge.maf.harbor import write_task
from forge.maf.selfcheck import selfcheck

# Dimensions whose CLI must read the scenario at runtime inside the agent
# container, so the scenario is necessarily in the agent's image. Relocating the
# module (as static dimensions do) cannot fix them; only the Plan 2 sidecar can.
# Rendering them would emit data whose reward is obtainable by reading the answer.
QUARANTINED = {
    "theory-of-mind": (
        "ground truth ships in the agent image; needs the Plan 2 sidecar. "
        "The construct is also degenerate: the instruction states the optimal "
        "algorithm (asks == q_opt on 12/12 sweep runs)."
    ),
    "failure-recovery": (
        "ground truth ships in the agent image; needs the Plan 2 sidecar."
    ),
}


def registry() -> dict:
    reg = {}
    from forge.maf.dimensions import scheduling

    reg[scheduling.DIM.NAME] = scheduling.DIM
    for name in ("failure_recovery", "theory_of_mind"):
        try:
            mod = __import__(f"forge.maf.dimensions.{name}", fromlist=["DIM"])
            reg[mod.DIM.NAME] = mod.DIM
        except Exception:
            pass
    return reg


def gen(args) -> dict:
    reg = registry()
    if args.dim in QUARANTINED:
        raise SystemExit(
            f"refusing to render quarantined dimension {args.dim!r}: "
            f"{QUARANTINED[args.dim]}"
        )
    if args.dim not in reg:
        raise SystemExit(f"unknown dimension {args.dim!r}; have {sorted(reg)}")
    dim = reg[args.dim]
    difficulty = dim.DIFFICULTY_PRESETS.get(args.difficulty)
    if difficulty is None:
        raise SystemExit(
            f"unknown difficulty {args.difficulty!r}; "
            f"have {sorted(dim.DIFFICULTY_PRESETS)}"
        )

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    shipped, rejected = [], []
    for i in range(args.n):
        seed = args.seed + i
        inst = dim.generate(seed, difficulty)
        rep = selfcheck(dim, inst)
        if rep.ok:
            d = write_task(dim, inst, out, f"{seed:04d}")
            shipped.append(str(d))
        else:
            rejected.append(
                {"seed": seed,
                 "failed": [k for k, v in rep.checks.items() if not v]}
            )
    summary = {
        "dim": args.dim,
        "requested": args.n,
        "shipped": len(shipped),
        "rejected": rejected,
        "dirs": shipped,
    }
    print(json.dumps(summary, indent=2))
    return summary


def main(argv=None):
    p = argparse.ArgumentParser(prog="forge")
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gen", help="generate tasks")
    g.add_argument("--dim", required=True)
    g.add_argument("--seed", type=int, default=0)
    g.add_argument("--n", type=int, default=1)
    g.add_argument("--difficulty", default="medium")
    g.add_argument("--out", default="tasks")
    g.set_defaults(func=gen)
    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main(sys.argv[1:])
