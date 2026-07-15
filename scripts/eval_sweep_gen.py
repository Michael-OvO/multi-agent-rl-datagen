"""Build the eval sweep instance set + zero-cost baselines.

Generates a fixed set of tasks: 3 dimensions x 3 difficulties x 2 seeds, each
gated by the CLEAN/VALID selfcheck. For every instance it records the oracle
reward (=1.0) and the cheater-panel rewards (the shortcut baselines) in
``sweep/baselines.json``. Real-model rewards are added later by the aggregator.

Both models are then run against this SAME instance set, so comparisons are fair.
"""

import importlib
import json
import shutil
from pathlib import Path

from forge.maf.harbor import write_task
from forge.maf.selfcheck import selfcheck

DIMS = ["scheduling", "failure_recovery", "theory_of_mind"]
DIFFICULTIES = ["easy", "medium", "hard"]
SEEDS_PER_CELL = 2
MAX_SCAN = 60  # seeds to scan per cell looking for SEEDS_PER_CELL that pass selfcheck

OUT = Path("sweep/instances")


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    baselines = {}
    for mod_name in DIMS:
        dim = importlib.import_module(f"forge.maf.dimensions.{mod_name}").DIM
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
                write_task(dim, inst, OUT, task_id)
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

    Path("sweep/baselines.json").write_text(json.dumps(baselines, indent=2))
    n = len(baselines)
    print(f"generated {n} gated instances into {OUT}")
    print("baselines written to sweep/baselines.json")
    # quick sanity: every oracle == 1.0
    bad = [k for k, v in baselines.items() if v["oracle"] != 1.0]
    print("oracle==1.0 for all:", not bad, ("" if not bad else f"BAD: {bad}"))


if __name__ == "__main__":
    main()
