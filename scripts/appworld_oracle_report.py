"""Collect Harbor oracle runs into one evidence file.

A Harbor task ships a `solution/` so that someone can check the task is solvable.
Until 2026-07-15 these tasks shipped `exit 1`, on the claim that there was nothing
to replay. There was: the decomposition. The real objection was that replaying it
runs live models and is therefore nondeterministic -- a cost to state, not a
reason to ship no solution.

So: run it, and write down what happened, including when it fails.

    harbor run --agent oracle --path tasks/appworld-star-docs-binf-2a163ab_1 \\
        --env-file .env -o jobs/oracle-1
    python -m scripts.appworld_oracle_report jobs/oracle-*

Reads each job's verifier breakdown and writes sweep/appworld_oracle.json.
`reward=1.0` means AppWorld's own six per-requirement tests all passed -- not a
metric of ours.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

OUT = Path("sweep/appworld_oracle.json")


def main(argv: list[str]) -> None:
    if not argv:
        raise SystemExit(__doc__)

    rows = []
    for job in argv:
        for breakdown in sorted(Path().glob(f"{job}/*/*/verifier/breakdown.json")):
            data = json.loads(breakdown.read_text())
            # .../<task dir>/<timestamp>/<harbor's hashed name>/verifier/...
            # The hashed name does not say which task it was; the job directory
            # does, and that is the whole point of an evidence file.
            rows.append({
                "task": breakdown.parents[3].name,
                "trial": breakdown.parents[1].name,
                "success": data["success"],
                "partial": data["partial"],
                "passes": data["passes"],
                "failures": data["failures"],
                "delegations": data["delegations"],
                # Non-zero would mean a reference brief pushed a specialist out
                # of its app -- the reference paths should never do that.
                "blocked": sum(e.get("blocked", 0) for e in data.get("ledger", [])),
                "reports": [e["report"] for e in data.get("ledger", [])],
            })

    if not rows:
        raise SystemExit(f"no verifier breakdowns under {argv}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, indent=1))

    passed = sum(r["success"] for r in rows)
    for r in rows:
        print(f"{r['task']}: success={r['success']} partial={r['partial']} "
              f"({r['passes']}/{r['passes'] + r['failures']}) "
              f"delegations={r['delegations']} blocked={r['blocked']}")
    print(f"\n{passed}/{len(rows)} oracle solutions passed -> {OUT}")


if __name__ == "__main__":
    main(sys.argv[1:])
