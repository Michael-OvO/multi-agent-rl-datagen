"""Build the eval sweep instance set + zero-cost baselines.

Generates a fixed set of tasks -- every non-quarantined dimension x 3
difficulties x 2 seeds -- each gated by the CLEAN/VALID selfcheck. For every
instance it records the oracle reward (=1.0) and the cheater-panel rewards
(the shortcut baselines) in ``sweep/baselines.json``. Real-model rewards are
added later by the aggregator.

Both models are then run against this SAME instance set, so comparisons are fair.

Quarantine: this script calls ``write_task`` directly rather than going
through ``forge gen``, so it does not inherit forge_cli's refusal to render a
quarantined dimension. It therefore imports ``QUARANTINED`` itself (never a
copy of the list -- one source of truth, so lifting the quarantine here needs
no edit) and skips those dimensions by name.

Destructive-failure rule: instances are built into a staging directory and
only swapped into place once the whole run has succeeded. An earlier version
wiped ``sweep/instances/`` at startup and then died on the first quarantined
dimension, destroying the sweep set it could no longer rebuild.
"""

import importlib
import json
import shutil
import tempfile
from pathlib import Path

from forge.forge_cli import QUARANTINED
from forge.maf.harbor import write_task
from forge.maf.selfcheck import selfcheck

DIMS = ["scheduling", "failure_recovery", "theory_of_mind"]
DIFFICULTIES = ["easy", "medium", "hard"]
SEEDS_PER_CELL = 2
MAX_SCAN = 60  # seeds to scan per cell looking for SEEDS_PER_CELL that pass selfcheck

OUT = Path("sweep/instances")


def dimensions_to_generate() -> list:
    """The DIMs this script may render: everything in DIMS not quarantined.

    Filtered by ``dim.NAME`` against the live QUARANTINED dict rather than by
    module name against a second hardcoded list, so the quarantine has exactly
    one definition and un-quarantining a dimension re-includes it here for free.
    """
    dims = []
    for mod_name in DIMS:
        dim = importlib.import_module(f"forge.maf.dimensions.{mod_name}").DIM
        if dim.NAME in QUARANTINED:
            print(f"skipping quarantined dimension {dim.NAME}: {QUARANTINED[dim.NAME]}")
            continue
        dims.append(dim)
    return dims


def _build(out_dir: Path) -> dict:
    baselines = {}
    for dim in dimensions_to_generate():
        for difficulty in DIFFICULTIES:
            preset = dim.DIFFICULTY_PRESETS[difficulty]
            found = 0
            for seed in range(MAX_SCAN):
                if found >= SEEDS_PER_CELL:
                    break
                inst = dim.generate(seed, preset)
                rep = selfcheck(dim, inst)
                if not rep.ok:
                    continue
                task_id = f"{difficulty}-{seed:04d}"
                write_task(dim, inst, out_dir, task_id)
                name = f"{dim.NAME}-{task_id}"
                cheaters = {
                    n: round(dim.verify(inst, dim.run_policy(inst, p)).reward, 3)
                    for n, p in dim.CHEATERS.items()
                }
                oracle = dim.verify(inst, dim.run_policy(inst, dim.ORACLE)).reward
                baselines[name] = {
                    "dim": dim.NAME,
                    "difficulty": difficulty,
                    "seed": seed,
                    "oracle": round(oracle, 3),
                    "cheaters": cheaters,
                    "cheater_max": round(max(cheaters.values()), 3),
                }
                found += 1
            if found < SEEDS_PER_CELL:
                raise SystemExit(
                    f"only {found}/{SEEDS_PER_CELL} passing seeds for "
                    f"{dim.NAME}/{difficulty} in {MAX_SCAN} scans"
                )
    return baselines


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".instances-staging-", dir=OUT.parent))
    try:
        baselines = _build(staging)
    except BaseException:
        # Nothing generated is worth keeping, but the EXISTING set is: leave
        # sweep/instances (and baselines.json, which describes it) untouched.
        shutil.rmtree(staging, ignore_errors=True)
        raise

    # Only now, with the whole set built and gated, is it safe to destroy the
    # previous one.
    if OUT.exists():
        shutil.rmtree(OUT)
    staging.rename(OUT)

    Path("sweep/baselines.json").write_text(json.dumps(baselines, indent=2))
    n = len(baselines)
    print(f"generated {n} gated instances into {OUT}")
    print("baselines written to sweep/baselines.json")
    # quick sanity: every oracle == 1.0
    bad = [k for k, v in baselines.items() if v["oracle"] != 1.0]
    print("oracle==1.0 for all:", not bad, ("" if not bad else f"BAD: {bad}"))


if __name__ == "__main__":
    main()
