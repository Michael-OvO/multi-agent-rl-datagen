"""Where the floor actually is, now that the answer-type fix moved it.

Before the fix (§5.3), an action task's do-nothing score was 1/6 = 0.167: one
requirement ("no new transaction was added") passes for free. The fix submits
`answer=None` for action tasks, which is the ground truth's own answer -- so
`assert answers match` now **also** passes for free, and the floor is 2/6 = 0.333.

That matters more than it looks. `WRITEUP.md` §4 reports every partitioned
configuration at exactly **0.333**. If the floor is also 0.333, then the fix
raised the floor and the measured scores by the same amount, and "1.000 → 0.333"
is not a partial drop -- it is a drop *to the floor*. The partitioned Main is
scoring what it would score by doing nothing at all.

This is cheap to settle and needs no LLM: open the task, submit nothing but the
answer, evaluate. That is the entire probe.

    APPWORLD_ROOT=$PWD python -m scripts.appworld_donothing_probe

Measured 2026-07-15 on all three shipped tasks: passes=2, failures=4, 0.333.
"""

from __future__ import annotations

import json
from pathlib import Path

#: The tasks that render with a reference solution. Keep in step with
#: forge/appworld/reference.py.
TASK_IDS = ("2a163ab_1", "2a163ab_2", "2a163ab_3")

OUT = Path("sweep/appworld_donothing.json")


def main() -> None:
    from appworld import AppWorld

    rows = []
    for task_id in TASK_IDS:
        with AppWorld(task_id=task_id, experiment_name="donothing_probe",
                      ground_truth_mode="minimal") as world:
            # The whole "agent": submit the answer an action task expects and
            # touch nothing else.
            world.execute("apis.supervisor.complete_task(answer=None, status='success')")
            ev = world.evaluate().to_dict()

        passes, failures = len(ev.get("passes", [])), len(ev.get("failures", []))
        total = passes + failures
        rows.append({
            "task_id": task_id,
            "agent": "do-nothing",
            "answer": None,
            "passes": passes,
            "failures": failures,
            "partial": round(passes / total, 3) if total else 0.0,
            "success": bool(ev.get("success")),
        })
        print(f"{task_id}: passes={passes} failures={failures} "
              f"partial={rows[-1]['partial']}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, indent=1))
    print(f"\nwrote {OUT}")

    floor = {r["partial"] for r in rows}
    print(f"do-nothing floor: {floor}")
    print("WRITEUP.md §5 reports every partitioned config at 0.333. If that "
          "is this number, the partitioned configs are on the floor.")


if __name__ == "__main__":
    main()
