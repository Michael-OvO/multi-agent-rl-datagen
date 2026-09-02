"""Run the full cell grid across every admitted seamful Gaia2 scenario.

    uv run python -m scripts.gaia2_campaign --label full --workers 3

For each unique seamful scenario (mini + adaptability, the 37 the admission
sweeps measured), runs the OPEN control and the three ability cells through
`scripts.gaia2_cell_run` in the dedicated `.venv-gaia2` interpreter. The
judge follows the audit's finding: reply-conditioned scenarios (whose later
phases only unlock when the judge's turn condition matches) run under
Gaia2's official soft judge; unconditioned scenarios run under the
deterministic scripted judge.

Resumable by construction: every run writes its own labelled, timestamped
trajectory, and a cell whose trajectory for this label already exists is
skipped -- kill the campaign and relaunch it freely. `--dry-run` prints the
work list and prices nothing.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from forge.abilities import Ability, config_for
from forge.appworld.partition import control_for
from forge.gaia2.mine import admit
from scripts.embed_logs import try_refresh

ROOT = Path(__file__).resolve().parents[1]
GAIA2_PY = ROOT / ".venv-gaia2" / "bin" / "python"

#: None is the OPEN control; the rest are the one-knob ability cells.
GRID = (None, Ability.DISCOVERY, Ability.CONTEXT_TRANSFER,
        Ability.DELEGATION_ECONOMY)


def eligible(span, scripted_only: bool) -> bool:
    """Admission, plus the optional judge-uniform restriction.

    `--scripted-only` exists because the grader is welded to the scenario:
    reply-conditioned scenarios can only run under the soft judge, and in the
    v3 campaign that judge's column was all zeros -- so every cross-arm
    comparison rode on the 5 of 37 scenarios the deterministic verifier
    grades. A seed spent under this flag buys 20 cells that can actually
    move, instead of 148 of which 128 are structurally pinned to zero.
    """
    if not (span.usable and span.seamful):
        return False
    if span.roster_blind:
        # The partition provably omits a fact the gold writes consume (see
        # mine.BlindFact): every seat is locked out of it, so every episode
        # is a guaranteed failure. v4 bought four of these on one scenario.
        return False
    return not (scripted_only and span.reply_conditioned)


def scenario_paths() -> dict[str, Path]:
    """Every unique seamful scenario with a fetched file, mini first."""
    seen: dict[str, Path] = {}
    for cells_file, split in (("sweep/gaia2_cells.json", "mini"),
                              ("sweep/gaia2_cells_adaptability.json", "adaptability")):
        for cell in json.loads((ROOT / cells_file).read_text()):
            sid = cell["scenario_id"]
            if sid in seen:
                continue
            path = ROOT / "gaia2_data" / split / f"{sid}.json"
            if path.exists():
                seen[sid] = path
    return seen


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--label", default="full")
    ap.add_argument("--workers", type=int, default=3,
                    help="concurrent episodes; the org rate ceiling makes "
                         "more than ~4 counterproductive")
    ap.add_argument("--out", default="output/rollouts")
    ap.add_argument("--judge-model", default="gpt-5.6-sol",
                    help="soft-judge model for reply-conditioned scenarios")
    ap.add_argument("--scripted-only", action="store_true",
                    help="run only scenarios the deterministic scripted judge "
                         "can grade (5 of the 37): a judge-uniform grid, so "
                         "arm differences cannot hide behind the soft judge's "
                         "zero column")
    target = ap.add_mutually_exclusive_group()
    target.add_argument(
        "--economy-target",
        type=int,
        default=None,
        help="use one explicit soft bN target for every economy cell",
    )
    target.add_argument(
        "--economy-target-offset",
        type=int,
        default=0,
        help="add this amount to each task-derived economy heuristic",
    )
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if args.economy_target is not None and args.economy_target < 1:
        ap.error("--economy-target must be positive")

    jobs = []
    skipped = 0
    for sid, path in sorted(scenario_paths().items()):
        span = admit(json.loads(path.read_text()))
        if not eligible(span, args.scripted_only):
            continue
        soft = span.reply_conditioned
        economy_target = (
            args.economy_target
            if args.economy_target is not None
            else max(1, span.delegation_target + args.economy_target_offset)
        )
        for ability in GRID:
            config = (control_for(span.roster) if ability is None
                      else config_for(ability, span.roster,
                                      budget_target=economy_target))
            existing = list((ROOT / args.out).glob(
                f"gaia2__{sid}__{config.label}*__{args.label}__*.json"))
            if existing:
                skipped += 1
                continue
            cmd = [str(GAIA2_PY), "-m", "scripts.gaia2_cell_run",
                   "--scenario", str(path),
                   "--ability", "control" if ability is None else ability.value,
                   "--label", args.label, "--out", args.out]
            if ability is Ability.DELEGATION_ECONOMY:
                cmd += ["--economy-target", str(economy_target)]
            if soft:
                cmd += ["--judge-model", args.judge_model]
            jobs.append((sid, config.label, soft, cmd))

    print(f"{len(jobs)} cells to run ({skipped} already done, resumed past)")
    if args.dry_run:
        for sid, label, soft, _ in jobs:
            print(f"  {sid:34} {label:18} judge={'soft' if soft else 'scripted'}")
        return

    def run_one(job):
        sid, label, soft, cmd = job
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        lines = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()
        verdict = next((ln for ln in reversed(lines) if ln.startswith("verdict")),
                       lines[-1] if lines else "(no output)")
        return sid, label, r.returncode, verdict[:110]

    done = failed = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(run_one, job) for job in jobs]
        for future in as_completed(futures):
            sid, label, code, verdict = future.result()
            done += 1
            if code != 0:
                failed += 1
            print(f"[{done}/{len(jobs)}] {sid} {label}: "
                  f"{'ERROR rc=' + str(code) if code else verdict}", flush=True)
    print(f"campaign complete: {done} ran, {failed} errored")
    # The page follows the results without anyone remembering embed_logs.
    # A refresh failure is reported, never raised: the rollouts are on disk.
    try_refresh(args.label)


if __name__ == "__main__":
    main()
