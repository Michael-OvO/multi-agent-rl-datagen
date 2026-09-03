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
skipped -- kill the campaign and relaunch it freely. Before running, the
campaign renders every cell of the grid as a Harbor task under `tasks/`
(`forge.gaia2.harbor.render_grid`), so the shipped tasks are always the
cells that were measured. `--dry-run` prints the work list, renders nothing
and prices nothing.
"""

from __future__ import annotations

import argparse
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from forge.abilities import Ability
from forge.gaia2.grid import cells
from forge.gaia2.harbor import render_grid
from scripts.embed_logs import try_refresh

ROOT = Path(__file__).resolve().parents[1]
GAIA2_PY = ROOT / ".venv-gaia2" / "bin" / "python"


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

    grid = cells(ROOT, scripted_only=args.scripted_only,
                 economy_target=args.economy_target,
                 economy_target_offset=args.economy_target_offset)
    jobs = []
    skipped = 0
    for cell in grid:
        existing = list((ROOT / args.out).glob(
            f"gaia2__{cell.scenario_id}__{cell.constraints.label}*__{args.label}__*.json"))
        if existing:
            skipped += 1
            continue
        cmd = [str(GAIA2_PY), "-m", "scripts.gaia2_cell_run",
               "--scenario", str(cell.scenario_path),
               "--ability", "control" if cell.ability is None else cell.ability.value,
               "--label", args.label, "--out", args.out]
        if cell.ability is Ability.DELEGATION_ECONOMY:
            cmd += ["--economy-target", str(cell.economy_target)]
        if cell.soft_judge:
            cmd += ["--judge-model", args.judge_model]
        jobs.append((cell.scenario_id, cell.constraints.label, cell.soft_judge, cmd))

    print(f"{len(jobs)} cells to run ({skipped} already done, resumed past)")
    if args.dry_run:
        for sid, label, soft, _ in jobs:
            print(f"  {sid:34} {label:18} judge={'soft' if soft else 'scripted'}")
        return

    # The shipped form follows the measured form: every cell in this grid,
    # done or not, is rendered from the same scenario and constraints it
    # runs under, so tasks/ cannot lag what the campaign measured.
    rendered = render_grid(grid, ROOT / "tasks")
    print(f"rendered {len(rendered)} tasks under tasks/")

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
