"""Faithful local dry-run of the shipped tasks' oracle -> verify flow.

Executes exactly what the container would (oracle produces a submission, the
copied dimension module verifies it), but with local paths and importing ONLY
each task's ``environment/lib`` — no access to the ``forge`` package. Proves the
shipped artifacts are self-contained and score the oracle at 1.0, without Docker.
"""

import importlib.util
import json
import re
import sys
from pathlib import Path


def _import_maf_dim(lib_dir: Path):
    # Load the copied maf_core + maf_dim in isolation (as the container does).
    for name in ("maf_core", "maf_dim"):
        spec = importlib.util.spec_from_file_location(name, lib_dir / f"{name}.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    return sys.modules["maf_dim"]


def _oracle_submission(task: Path, cfg: dict, maf_dim):
    if not cfg["interactive"]:
        # Static: parse the schedule embedded in solve.sh (what the oracle writes).
        solve = (task / "solution" / "solve.sh").read_text()
        return json.loads(solve[solve.index("["):solve.rindex("]") + 1])
    # Interactive: run the oracle policy against a fresh env (what solve.sh does).
    inst = json.load(open(task / "environment" / "scenario.json"))
    return maf_dim.run_policy(inst, maf_dim.ORACLE)


def _full_instance(task: Path, cfg: dict) -> dict:
    if cfg["interactive"]:
        return json.load(open(task / "environment" / "scenario.json"))
    inst = json.load(open(task / "environment" / "task.json"))
    inst.update(json.load(open(task / "tests" / "ground_truth.json")))
    return inst


def main():
    tasks = sorted(p for p in Path("tasks").iterdir() if p.is_dir())
    ok = True
    for task in tasks:
        for name in list(sys.modules):
            if name in ("maf_core", "maf_dim"):
                del sys.modules[name]
        cfg = json.load(open(task / "tests" / "verify_config.json"))
        maf_dim = _import_maf_dim(task / "environment" / "lib")
        submission = _oracle_submission(task, cfg, maf_dim)
        rb = maf_dim.verify(_full_instance(task, cfg), submission)
        status = "OK " if rb.reward == 1.0 else "FAIL"
        if rb.reward != 1.0:
            ok = False
        print(f"[{status}] {task.name:28s} oracle reward = {rb.reward} ({rb.subscores})")
    print("\nALL PASS" if ok else "\nFAILURES PRESENT")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
