"""Run one Gaia2 cell end to end: scenario -> episode -> verdict -> trajectory.

This is the first executable path through a rendered Gaia2 cell: the miner
derives the roster, `forge/abilities.config_for` turns the ability into its
one-knob constraint configuration, `forge/gaia2/runtime.run_main` runs the
Main and its specialists over the live environment, and Gaia2's own
write-action judge prices the result. The full trajectory -- every message,
delegation, tool call and wait -- is written as one JSON file, which is the
input format of the single-page viewer (trajectory_viewer.html).

The official harness needs pydantic 2 and the pinned main environment
carries AppWorld's pydantic 1, so this runs under the dedicated environment:

    .venv-gaia2/bin/python -m scripts.gaia2_cell_run \\
        --scenario gaia2_data/mini/<scenario_id>.json \\
        --ability context-transfer --out output/rollouts

`--ability control` renders the OPEN ablation twin. Models default to the
same frontier series for both roles; forge/models.require_specialist_parity
refuses a downgraded specialist before anything runs.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from forge.gaia2.mine import admit
from scripts._env import require_api_key

CONTROL = "control"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True, help="one fetched scenario JSON")
    parser.add_argument(
        "--ability", default=CONTROL,
        choices=(CONTROL, "capability-discovery", "context-transfer",
                 "delegation-economy"))
    parser.add_argument("--main-model", default=None,
                        help="defaults to forge.gaia2.runtime.DEFAULT_MODEL")
    parser.add_argument("--sub-model", default=None,
                        help="defaults to the main model (parity by construction)")
    parser.add_argument("--allow-sub-downgrade", action="store_true",
                        help="explicitly permit a specialist below the Main's "
                             "model class; the trajectory still records both models")
    parser.add_argument("--judge-model", default=None,
                        help="run Gaia2's official judge as shipped (graph judge "
                             "plus LLM soft-checkers) with this model; default is "
                             "the deterministic scripted judge. Required in "
                             "practice for reply-conditioned scenarios -- see "
                             "forge/gaia2/mine.py")
    parser.add_argument("--label", default=None,
                        help="extra filename suffix, so a verification re-run "
                             "never overwrites the trajectory it is checking")
    parser.add_argument("--max-steps", type=int, default=40)
    parser.add_argument(
        "--economy-target",
        type=int,
        default=None,
        help="override the task-derived soft bN delegation target",
    )
    parser.add_argument("--out", default="output/rollouts")
    args = parser.parse_args(argv)
    if args.economy_target is not None and args.economy_target < 1:
        parser.error("--economy-target must be positive")
    if args.economy_target is not None and args.ability != "delegation-economy":
        parser.error("--economy-target applies only to delegation-economy")

    # Admission before the API key and before the .venv-gaia2 imports: a
    # scenario this refuses must be refused under any interpreter, with or
    # without credentials -- the campaign filters blind scenarios, but this
    # script is the documented single-cell entry point and used to check
    # only `usable`, so a direct invocation could still buy a
    # guaranteed-failure episode.
    scenario_path = Path(args.scenario)
    scenario = json.loads(scenario_path.read_text())
    span = admit(scenario)
    if not span.usable:
        raise SystemExit(f"{span.scenario_id}: roster {span.roster} has nothing "
                         "to coordinate; this scenario was never admitted")
    if span.roster_blind:
        facts = ", ".join(
            f"{f.arg} needs {f.leaf!r} (only in {'/'.join(f.sources)})"
            for f in span.roster_blind[:3])
        raise SystemExit(
            f"{span.scenario_id}: roster-blind, refusing to spend an episode "
            f"on it -- the gold writes consume facts no seat can read: "
            f"{facts}")

    require_api_key()

    # Imports that need .venv-gaia2 live below the argparse so that --help
    # works anywhere and the failure mode for the wrong interpreter is the
    # loud ImportError from are_world's docstringed import block.
    from openai import OpenAI

    from forge.abilities import Ability, config_for
    from forge.appworld.partition import control_for
    from forge.gaia2.are_world import open_world
    from forge.gaia2.runtime import (
        DEFAULT_MODEL,
        EpisodeLog,
        delegation_economy_features,
        run_main,
    )

    target = (
        span.delegation_target
        if args.economy_target is None
        else args.economy_target
    )
    config = (control_for(span.roster) if args.ability == CONTROL
              else config_for(Ability(args.ability), span.roster,
                              budget_target=target))
    main_model = args.main_model or DEFAULT_MODEL

    print(f"{span.scenario_id}: config {config.label}, roster {span.roster}, "
          f"judge {args.judge_model or 'scripted'}")
    world = open_world(scenario_path, judge_model=args.judge_model)
    started = time.time()
    try:
        task = world.first_task()
        if task is None:
            raise SystemExit(f"{span.scenario_id}: the scenario never sent a "
                             "user task; nothing to run")
        # Explicit, finite, and generous: the slowest observed reasoning turn
        # in a v4 episode was ~3 minutes, so 300s catches a dead connection
        # without cutting off a live long thought. Retries reconnect rather
        # than wait -- chat completions are stateless, so a retried request
        # costs at most a duplicate turn, never corrupted state. Library
        # defaults left two v4 episodes blocked in SSL_read for nine hours.
        client = OpenAI(timeout=300.0, max_retries=3)
        log = EpisodeLog()
        answer = run_main(client, world, task, config, log,
                          model=main_model, sub_model=args.sub_model,
                          max_steps=args.max_steps,
                          allow_sub_downgrade=args.allow_sub_downgrade)
        verdict = world.verdict()
    finally:
        world.stop()

    row = {
        "kind": "gaia2-episode",
        "scenario_id": span.scenario_id,
        "category": (scenario.get("_gaia2") or {}).get("category"),
        "ability": None if args.ability == CONTROL else args.ability,
        "config": config.label,
        "roster": list(span.roster),
        # Non-zero means later phases unlock only if the judge's turn
        # condition matches -- under the scripted judge such scenarios can
        # freeze mid-episode (see forge/gaia2/mine.py, the audit finding).
        "conditioned_env_events": span.conditioned_env_events,
        "delegation_target_heuristic": span.delegation_target,
        "main_model": main_model,
        "sub_model": args.sub_model or main_model,
        "answer": answer,
        "judge": args.judge_model or "scripted",
        "label": args.label,
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(started)),
        "verdict": verdict,
        "seconds": round(time.time() - started, 1),
        **log.as_dict(),
        **delegation_economy_features(
            log.delegation_target,
            log.delegations,
            task_success=verdict["success"],
        ),
    }
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    # Every run is its own evidence file: the start stamp in the name means a
    # re-run can never overwrite the trajectory it should be compared with.
    judge_tag = "" if args.judge_model is None else "__softjudge"
    label_tag = f"__{args.label}" if args.label else ""
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(started))
    out = out_dir / (f"gaia2__{span.scenario_id}__{config.label}"
                     f"{judge_tag}{label_tag}__{stamp}.json")
    out.write_text(json.dumps(row, indent=1))
    print(f"answer: {answer}")
    print(f"verdict: {'success' if verdict['success'] else 'failure'}"
          f" -- {out} ({out.stat().st_size / 1e3:.0f} kB)")


if __name__ == "__main__":
    main()
