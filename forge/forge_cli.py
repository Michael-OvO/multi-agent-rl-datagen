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


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def registry() -> dict:
    """The dimensions `gen` can actually render.

    It used to import the quarantined two as well, under a bare
    `except Exception: pass`, so that `--dim bogus` answered
    `have ['failure-recovery', 'parallel-scheduling', 'theory-of-mind']` -- two
    of which `gen` refuses four lines later, and both of which are refused
    *before* this dict is consulted. So the import bought a wrong error message,
    and the bare `except` would have swallowed a genuine ImportError in the one
    dimension that does ship. `QUARANTINED` names them, and their modules stay
    importable for `selfcheck` and the tests that measure them.
    """
    from forge.maf.dimensions import scheduling

    return {scheduling.DIM.NAME: scheduling.DIM}


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
    g.add_argument(
        "--dim",
        required=True,
        help=(
            "dimension to render (available: parallel-scheduling; "
            "quarantined: failure-recovery, theory-of-mind)"
        ),
    )
    g.add_argument("--seed", type=int, default=0)
    g.add_argument("--n", type=_positive_int, default=1, help="task count (at least 1)")
    g.add_argument(
        "--difficulty",
        default="medium",
        help="difficulty preset (easy, medium, hard)",
    )
    g.add_argument("--out", default="tasks")
    g.set_defaults(func=gen)
    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main(sys.argv[1:])
