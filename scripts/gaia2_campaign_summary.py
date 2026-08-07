"""Summarize a Gaia2 campaign into one evidence file. (no LLM)

    uv run python -m scripts.gaia2_campaign_summary --label full

Reads every trajectory carrying the label, keeps the newest run per
(scenario, ability) so re-runs under corrected configurations supersede
their predecessors without erasing them, and writes
sweep/gaia2_<label>_campaign.json: the deduplicated grid rows plus the
summary a reader needs first -- verdicts and mean shaping signals by cell
type and judge, the pivot census, and the per-scenario verdict matrix.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def cell_type(config: str) -> str:
    if config.startswith("open"):
        return "control"
    if "names" in config:
        return "discovery"
    return "context" if config.endswith("binf") else "economy"


def _mean(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 3) if values else None


def summarize(rows) -> dict:
    """Verdicts and shaping signals by cell type, each split by judge.

    The split inside every arm is the point, not decoration. The grader is
    welded to the scenario -- reply-conditioned rows go to the soft judge,
    the rest to the scripted verifier -- so an arm's pooled success count
    mixes two graders over disjoint populations. In v3 that shape was misread
    twice in one sitting: pooled arm rates looked comparable while every
    success sat in the scripted column. The pooled number stays (it is what
    the campaign yielded), but never without its decomposition.
    """
    summary: dict = {}
    for t in ("control", "discovery", "context", "economy"):
        sub = [r for r in rows if r["cell_type"] == t]
        if not sub:
            continue
        entry = {
            "cells": len(sub),
            "success": sum(1 for r in sub if r["success"]),
            "by_judge": {
                j: {"cells": len(g), "success": sum(1 for r in g if r["success"])}
                for j in sorted({r["judge"] for r in sub})
                for g in [[r for r in sub if r["judge"] == j]]
            },
            "mean_partial_reward": _mean(r["partial_reward"] for r in sub),
            "pivot_kinds": dict(Counter(
                r["pivot_kind"] for r in sub if r["pivot_kind"])),
        }
        if t == "economy":
            entry["mean_economy_reward"] = _mean(
                r["delegation_economy_reward"] for r in sub)
        summary[t] = entry

    by_judge = defaultdict(lambda: [0, 0])
    for r in rows:
        by_judge[r["judge"]][0] += 1
        by_judge[r["judge"]][1] += r["success"]
    summary["by_judge"] = {
        j: {"cells": n, "success": s} for j, (n, s) in sorted(by_judge.items())}
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--label", default="full")
    args = ap.parse_args()

    newest: dict[tuple[str, str], dict] = {}
    for p in sorted((ROOT / "output" / "rollouts").glob("gaia2__*.json")):
        row = json.loads(p.read_text())
        if row.get("label") != args.label:
            continue
        row["trajectory"] = f"output/rollouts/{p.name}"
        key = (row["scenario_id"], row.get("ability") or "control")
        if key not in newest or str(row.get("started_at", "")) > str(
                newest[key].get("started_at", "")):
            newest[key] = row

    rows = []
    for row in newest.values():
        credit = row.get("credit") or {}
        rows.append({
            "scenario_id": row["scenario_id"],
            "cell_type": cell_type(row["config"]),
            "config": row["config"],
            "judge": row.get("judge", "scripted"),
            "success": row["verdict"]["success"],
            "answer": str(row.get("answer", ""))[:120],
            "partial_reward": credit.get("partial_reward"),
            "coverage": credit.get("coverage"),
            "pivot_kind": credit.get("pivot_kind"),
            "delegations": row.get("delegations"),
            "delegation_target": row.get("delegation_target"),
            "delegation_economy_reward": row.get("delegation_economy_reward"),
            "false_outages": row.get("false_outages"),
            "malformed": row.get("malformed"),
            "seconds": row.get("seconds"),
            "started_at": row.get("started_at"),
            "trajectory": row["trajectory"],
        })
    rows.sort(key=lambda r: (r["scenario_id"], r["cell_type"]))

    summary = summarize(rows)

    matrix = defaultdict(dict)
    for r in rows:
        matrix[r["scenario_id"]][r["cell_type"]] = (
            "success" if r["success"] else "failure")

    out = {
        "note": (
            f"The '{args.label}' campaign, deduplicated to the newest run per "
            "(scenario, ability): every seamful scenario from the mini and "
            "adaptability splits under the four-cell grid, reply-conditioned "
            "scenarios soft-judged, unconditioned ones script-judged, with "
            "partial-credit/pivot shaping signals from "
            "sweep/gaia2_credit.json stamped per row. Single seed: this is "
            "the first pass of the five-seed sweep, not the sweep. Read each "
            "arm's by_judge split before its pooled success count: the "
            "grader is welded to the scenario population, so the pooled "
            "number mixes two graders over disjoint populations and prices "
            "neither."),
        "summary": summary,
        "verdict_matrix": dict(sorted(matrix.items())),
        "rows": rows,
    }
    dest = ROOT / "sweep" / f"gaia2_{args.label}_campaign.json"
    dest.write_text(json.dumps(out, indent=1))
    print(f"wrote {dest.relative_to(ROOT)} ({len(rows)} cells)")
    for t, s in summary.items():
        print(f"  {t}: {s}")


if __name__ == "__main__":
    main()
