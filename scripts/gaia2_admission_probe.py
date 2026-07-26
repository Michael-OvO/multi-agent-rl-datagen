"""Which Gaia2 mini scenarios can carry a partition? (no LLM)

The AppWorld numbers this mirrors: `appworld_span.json` (which tasks are
multi-app) and `appworld_seams.json` (which of those move a fact between
apps). Gaia2 collapses both into one pass because mining is state-provenance
rather than code analysis -- see forge/gaia2/mine.py for the rules and their
honesty caveats.

    uv run python -m scripts.gaia2_admission_probe

Reads gaia2_data/mini/*.json (produced by scripts.gaia2_fetch), writes
sweep/gaia2_mini_admission.json: one row per scenario, plus a printed
summary. Deterministic: re-emits byte-identically from the same data.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from forge.gaia2.mine import admit

IN_DIR = Path("gaia2_data/mini")
OUT = Path("sweep/gaia2_mini_admission.json")


def main() -> None:
    paths = sorted(IN_DIR.glob("*.json"))
    if not paths:
        raise SystemExit(
            f"no scenarios in {IN_DIR}. Run:\n"
            "  uv run --with pandas --with pyarrow python -m scripts.gaia2_fetch"
        )

    rows = []
    for path in paths:
        scenario = json.loads(path.read_text())
        span = admit(scenario)
        rows.append(
            {
                "scenario_id": span.scenario_id or path.stem,
                "category": scenario.get("_gaia2", {}).get("category"),
                "write_apps": list(span.write_apps),
                "roster": list(span.roster),
                "seams": [
                    {
                        "source": s.source,
                        "target": s.target,
                        "function": s.function,
                        "arg": s.arg,
                    }
                    for s in span.seams
                ],
                "usable": span.usable,
                "seamful": span.seamful,
            }
        )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, indent=1))

    total = len(rows)
    usable = sum(r["usable"] for r in rows)
    seamful = sum(r["seamful"] for r in rows)
    print(f"scenarios: {total}")
    print(f"usable (roster >= 2): {usable}  ({usable / total:.0%})")
    print(f"seamful (a fact crosses): {seamful}  ({seamful / total:.0%})")

    by_cat: Counter[str] = Counter()
    seamful_by_cat: Counter[str] = Counter()
    for r in rows:
        cat = r["category"] or "?"
        by_cat[cat] += 1
        if r["seamful"]:
            seamful_by_cat[cat] += 1
    for cat in sorted(by_cat):
        print(f"  {cat}: {seamful_by_cat[cat]}/{by_cat[cat]} seamful")

    pairs = Counter(
        (s["source"], s["target"]) for r in rows for s in r["seams"]
    )
    print("top seam edges:")
    for (src, dst), n in pairs.most_common(8):
        print(f"  {src} -> {dst}: {n}")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
