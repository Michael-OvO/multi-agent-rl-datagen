"""Stamp partial credit and pivots onto recorded trajectories. (no LLM)

    uv run python -m scripts.gaia2_credit_probe [--label full]

For every matching trajectory in output/rollouts/, computes the credit
annotation (forge/gaia2/credit.py) against the scenario's gold writes and
writes it back into the trajectory file as an additive `credit` block --
the viewer renders the pivot from it -- then writes the corpus evidence to
sweep/gaia2_credit.json: per-cell rows plus the summary a reward-formation
system needs (mean partial reward per cell type, the pivot-kind census, and
prefix/suffix sizes for pivot-style prefix replay).

Idempotent and deterministic: re-running recomputes every annotation.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from forge.gaia2.credit import assess, split_for_replay

ROOT = Path(__file__).resolve().parents[1]


def _scenario_file(scenario_id: str) -> Path | None:
    for split in ("mini", "adaptability"):
        p = ROOT / "gaia2_data" / split / f"{scenario_id}.json"
        if p.exists():
            return p
    return None


def cell_type(config: str) -> str:
    if config.startswith("open"):
        return "control"
    if "names" in config:
        return "discovery"
    return "context" if config.endswith("binf") else "economy"


def dest_for(label: str) -> Path:
    """The evidence file this label's rows belong in.

    The unqualified `gaia2_credit.json` is the full campaign's, cited by name
    in the README, both papers, and the viewer -- so only `--label full` may
    write it. Every other label gets its own file, following the campaign
    summary's `gaia2_<label>_campaign.json` convention. Before this function
    existed, a `--label v3` run silently replaced the full campaign's
    committed evidence with 112 rows of a different campaign.
    """
    name = ("gaia2_credit.json" if label == "full"
            else f"gaia2_{label}_credit.json")
    return ROOT / "sweep" / name


def note_for(label: str) -> str:
    return (
        f"Partial-credit and pivot annotations over the {label}-campaign "
        "trajectories (forge/gaia2/credit.py; deterministic, judge-free "
        "shaping signals stamped beside the benchmark's own verdict, "
        "never instead of it). partial_reward grades gold-write coverage "
        "and exact-argument fidelity so failed episodes with correct "
        "prefixes are not flattened to zero; pivot locates the first "
        "fault for prefix-replay training (freeze events[:pivot], "
        "optimize the suffix).")


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--label", default="full",
                    help="only trajectories carrying this run label")
    args = ap.parse_args()

    rows = []
    scenarios: dict[str, dict] = {}
    for p in sorted((ROOT / "output" / "rollouts").glob("gaia2__*.json")):
        row = json.loads(p.read_text())
        if row.get("label") != args.label:
            continue
        sid = row["scenario_id"]
        if sid not in scenarios:
            src = _scenario_file(sid)
            if src is None:
                continue
            scenarios[sid] = json.loads(src.read_text())
        credit = assess(scenarios[sid], row.get("events") or [])
        cut = split_for_replay(row.get("events") or [], credit)
        row["credit"] = credit.as_dict()
        p.write_text(json.dumps(row, indent=1))
        rows.append({
            "scenario_id": sid, "config": row["config"],
            "cell_type": cell_type(row["config"]),
            "judge": row.get("judge", "scripted"),
            "success": row["verdict"]["success"],
            **credit.as_dict(),
            "prefix_events": cut["prefix_events"],
            "suffix_events": cut["suffix_events"],
            "trajectory": f"output/rollouts/{p.name}",
        })

    by_type = defaultdict(list)
    for r in rows:
        by_type[r["cell_type"]].append(r)
    summary = {
        t: {
            "cells": len(rs),
            "mean_partial_reward": round(
                sum(r["partial_reward"] for r in rs) / len(rs), 3),
            "mean_coverage": round(sum(r["coverage"] for r in rs) / len(rs), 3),
            "pivot_kinds": dict(Counter(
                r["pivot_kind"] for r in rs if r["pivot_kind"])),
            "faultless": sum(1 for r in rs if r["pivot"] is None),
        }
        for t, rs in sorted(by_type.items())
    }
    out = {
        "note": note_for(args.label),
        "summary": summary,
        "rows": rows,
    }
    dest = dest_for(args.label)
    dest.write_text(json.dumps(out, indent=1))
    print(f"annotated {len(rows)} trajectories; wrote {dest.relative_to(ROOT)}")
    for t, s in summary.items():
        print(f"  {t:10} mean partial reward {s['mean_partial_reward']:.3f} "
              f"over {s['cells']} cells; pivots {s['pivot_kinds']}")


if __name__ == "__main__":
    main()
