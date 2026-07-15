"""Prove the drop belongs to the Main, not to a broken harness.

Every partitioned config scores 0.167, and 0.167 is *exactly* the do-nothing
score -- the `oracle` agent, which performs no action at all, scores
`passes=1, failures=5` on these tasks. A partitioned run landing precisely on
do-nothing looks far more like a broken harness than like a hard task, and that
reading has to be excluded before the number means anything.

The probe hands a specialist the brief the Main *should* have produced -- the
cross-app fact already filled in -- and checks the specialist can then do the
work. If it can, the harness is sound and the gap is the Main's orchestration.
If it cannot, the 0.167 is a bug and the dimension is invalid.

Measured 2026-07-15 on 2a163ab_1:
    one agent holding every API   -> 0.833
    specialist + a perfect brief  -> 0.833   <- this probe
    Main orchestrating for itself -> 0.167

Usage:
    python -m scripts.appworld_validity_probe
"""

from __future__ import annotations

import json
import os
from pathlib import Path

#: (task_id, specialist, a brief containing the cross-app fact the Main must
#: otherwise discover, expected minimum score). The names in the brief are the
#: real roommates, which live in `phone` -- the Main's whole job is to fetch them
#: and pass them on.
PROBES = [
    (
        "2a163ab_1",
        "venmo",
        "On my Venmo social feed, find every transaction from today that involves "
        "any of these people: Anthony Harrison, Anita Burch, Nicholas Weber. Like "
        "every one of them. Report how many you liked.",
        0.5,
    ),
]


def main() -> None:
    from appworld import AppWorld
    from openai import OpenAI

    from forge.appworld.runtime import RunLog, run_specialist

    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY not set")
    client = OpenAI()
    rows = []

    for task_id, specialist, brief, floor in PROBES:
        with AppWorld(task_id=task_id, experiment_name="validity_probe",
                      ground_truth_mode="full") as w:
            log = RunLog()
            report = run_specialist(client, w, specialist, brief, log,
                                    model="gpt-5.6-sol", max_turns=16)
            ev = w.evaluate().to_dict()
            passes, failures = len(ev.get("passes", [])), len(ev.get("failures", []))
            total = passes + failures
            partial = round(passes / total, 3) if total else 0.0

        ok = partial >= floor
        rows.append({"task_id": task_id, "specialist": specialist,
                     "partial": partial, "floor": floor, "harness_sound": ok,
                     "turns": log.specialist_turns, "report": report[:160]})
        print(f"{task_id} {specialist:8} partial={partial:.3f} "
              f"(floor {floor}) turns={log.specialist_turns} -> "
              f"{'HARNESS SOUND' if ok else 'HARNESS BROKEN — the 0.167 is a bug'}")
        print(f"   report: {report[:110]}")

    out = Path("sweep/appworld_validity.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=1))
    print(f"\nwrote {out}")

    if not all(r["harness_sound"] for r in rows):
        raise SystemExit(
            "A specialist could not do its job even with a perfect brief. The "
            "partitioned score measures a harness bug, not orchestration. Do not "
            "report the drop as a capability signal until this passes."
        )


if __name__ == "__main__":
    main()
