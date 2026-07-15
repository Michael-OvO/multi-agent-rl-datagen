"""Aggregate the eval sweep: real-model rewards + zero-cost baselines.

Reads sweep/runs/<model>/<timestamp>/<task>__<hash>/result.json for each model,
joins with sweep/baselines.json (oracle + cheater panel), and emits:
  - sweep/results.json  (per-task + per-cell aggregates)
  - a markdown summary on stdout (paste-ready for docs/RESEARCH.md)

No forge import needed — pure JSON.
"""

import json
import statistics
from pathlib import Path

MODELS = {"gpt56": "gpt-5.6", "gpt41": "gpt-4.1"}
DIFF_ORDER = {"easy": 0, "medium": 1, "hard": 2}


def _trial_reward(result_path: Path):
    r = json.loads(result_path.read_text())
    vr = r.get("verifier_result") or {}
    rew = (vr.get("rewards") or {}).get("reward")
    if rew is None:
        return None  # errored / crashed trial
    return float(rew)


def _model_rewards(model_dir: Path) -> dict:
    """task-name -> reward (None if crashed)."""
    out = {}
    if not model_dir.exists():
        return out
    for job in sorted(model_dir.iterdir()):
        if not job.is_dir():
            continue
        for trial in job.iterdir():
            rp = trial / "result.json"
            if not rp.exists():
                continue
            task = trial.name.rsplit("__", 1)[0]
            out[task] = _trial_reward(rp)
    return out


def main():
    baselines = json.loads(Path("sweep/baselines.json").read_text())
    model_rewards = {m: _model_rewards(Path(f"sweep/runs/{m}")) for m in MODELS}

    per_task = {}
    for task, meta in baselines.items():
        row = dict(meta)
        for m in MODELS:
            row[m] = model_rewards[m].get(task)
        per_task[task] = row

    # aggregate by (dim, difficulty)
    cells = {}
    for task, row in per_task.items():
        key = (row["dim"], row["difficulty"])
        cells.setdefault(key, []).append(row)

    def _mean(vals):
        vals = [0.0 if v is None else v for v in vals]  # crash counts as 0
        return round(statistics.mean(vals), 3) if vals else None

    agg = {}
    for (dim, diff), rows in cells.items():
        agg[f"{dim}/{diff}"] = {
            "dim": dim, "difficulty": diff, "n": len(rows),
            "oracle": _mean([r["oracle"] for r in rows]),
            "cheater_max": _mean([r["cheater_max"] for r in rows]),
            **{m: _mean([r[m] for r in rows]) for m in MODELS},
        }

    Path("sweep/results.json").write_text(
        json.dumps({"per_task": per_task, "aggregate": agg}, indent=2))

    # markdown
    print("### Mean reward by dimension x difficulty (n=2 seeds each)\n")
    print("| Dimension | Difficulty | oracle | gpt-5.6 | gpt-4.1 | cheater(max) |")
    print("|---|---|---|---|---|---|")
    for key in sorted(agg, key=lambda k: (agg[k]["dim"], DIFF_ORDER[agg[k]["difficulty"]])):
        a = agg[key]
        print(f"| {a['dim']} | {a['difficulty']} | {a['oracle']} | "
              f"{a['gpt56']} | {a['gpt41']} | {a['cheater_max']} |")
    # count crashes
    crashes = {m: sum(1 for r in per_task.values() if r[m] is None) for m in MODELS}
    print(f"\nCrashed/errored trials: {crashes} (counted as reward 0 in means)")


if __name__ == "__main__":
    main()
