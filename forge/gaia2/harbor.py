"""Render an admitted Gaia2 scenario + a constraint configuration into a
Harbor task.

Same isolation boundary as forge/appworld/harbor.py, for the same reasons:
the simulated world, the specialists, the oracle events and the judge live
in a sidecar; the Main's container gets the ~120-line `team` client and
nothing else. "The Main has no API access" is a property of the filesystem.

Two Gaia2-specific differences:

  * **The scenario ships in the task.** AppWorld's sidecar downloads its
    dataset at build time (unpinnable, and noted as such); a Gaia2 task
    carries its whole world -- initial app states, scheduled events, oracle
    writes -- as `environment/scenario.json`, so a rendered task rebuilds
    identically from its own directory.

  * **The protocol has a clock.** The `team` client grows `wait` (jump
    simulated time to the next event) and `fail` (the honest-failure
    channel), and `done` may answer "continued" -- Gaia2 scenarios schedule
    follow-up user turns to fire after the agent reports back.

The verifier is shared with AppWorld verbatim: `tests/verify.py` computes
nothing, it reads the sidecar's `/state` and writes the reward out, and that
holds for any substrate whose sidecar speaks the protocol.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from forge.appworld.harbor import _difficulty
from forge.appworld.partition import Constraints, Topology, Visibility
from forge.gaia2.runtime import (
    OBJECTIVE_ACTION_CONTRACT,
    OBJECTIVE_ACTION_CONTRACT_VERSION,
)

_RUNTIME = Path(__file__).parent / "container"
_APPWORLD = Path(__file__).parents[1] / "appworld"

#: What the sidecar imports from forge.gaia2: the specialist loop, the world
#: adapter over the official harness, and the miner (the package __init__
#: imports it). render.py and structure.py stay home -- nothing in the
#: container imports them.
SIDECAR_GAIA2_MODULES = ("__init__.py", "mine.py", "runtime.py", "are_world.py")

#: What the sidecar imports from forge.appworld: the Gaia2 runtime is built
#: on the AppWorld runtime's chat loop and constraint layer, so those travel
#: too. Same modules the AppWorld sidecar ships, which is not a coincidence.
SIDECAR_APPWORLD_MODULES = ("__init__.py", "partition.py", "runtime.py", "sandbox.py")

#: Every file a rendered task gets *verbatim* -- one manifest, walked by the
#: renderer and by the drift guard in test_gaia2_harbor.py, so a copy cannot
#: be added without being guarded (the AppWorld lesson, kept).
VERBATIM_COPIES = {
    "environment/Dockerfile.sidecar": _RUNTIME / "Dockerfile.sidecar",
    "environment/team": _RUNTIME / "team",
    "environment/server.py": _RUNTIME / "server.py",
    # Shared with AppWorld on purpose: the verifier computes nothing, so
    # there is exactly one of it.
    "tests/verify.py": _APPWORLD / "container" / "verify.py",
    "environment/maf_models.py": Path(__file__).parents[1] / "models.py",
    **{f"environment/maf_gaia2/{mod}": Path(__file__).parent / mod
       for mod in SIDECAR_GAIA2_MODULES},
    **{f"environment/maf_appworld/{mod}": _APPWORLD / mod
       for mod in SIDECAR_APPWORLD_MODULES},
}

_TASK_TOML = """schema_version = "1.3"
artifacts = []

[task]
name = "demo/gaia2-{label}-{scenario_id}"
description = "Multi-agent orchestration over Gaia2 ({roster}), {label}."
keywords = ["multi-agent", "rl", "orchestration", "gaia2"]
[[task.authors]]
name = "multi-agent-task-forge"

[metadata]
difficulty = "{difficulty}"
category = "agentic"
tags = ["multi-agent", "orchestration", "gaia2"]

[verifier]
timeout_sec = 600.0
collect = []

[verifier.env]

[agent]
timeout_sec = 1800.0

[environment]
network_mode = "public"
build_timeout_sec = 900.0
os = "linux"
mcp_servers = []

[environment.env]

[solution.env]
"""

_COMPOSE = """services:
  main:
    build:
      context: .
      dockerfile: Dockerfile
    command: sleep infinity
    depends_on:
      maf-env:
        # Wait for the sidecar to be READY, not merely started: importing the
        # simulation harness and running the scenario's oracle pass takes
        # seconds, and a verifier that fires first reports "cannot reach the
        # sidecar" on a task that was fine.
        condition: service_healthy

  maf-env:
    build:
      context: .
      dockerfile: Dockerfile.sidecar
    environment:
      MAF_CONFIG: '{config_json}'
      MAF_VERIFIER_TOKEN: "{token}"
      # Both roles default to the frontier series. The sidecar refuses to
      # start a specialist below the Main's model class (forge/models.py), so
      # overriding MAF_SUB_MODEL downward is a startup error, not a silent
      # downgrade of what the task measures -- unless the operator also sets
      # MAF_ALLOW_SUB_DOWNGRADE=1, which makes it a deliberate, labelled one.
      MAF_MAIN_MODEL: "${{MAF_MAIN_MODEL:-gpt-5.6-sol}}"
      MAF_SUB_MODEL: "${{MAF_SUB_MODEL:-gpt-5.6-sol}}"
      MAF_ALLOW_SUB_DOWNGRADE: "${{MAF_ALLOW_SUB_DOWNGRADE:-}}"
      OPENAI_API_KEY: "${{OPENAI_API_KEY}}"
    expose:
      - "8080"
    healthcheck:
      # /health, not /roster: /roster reaches the live world, and this fires
      # every 3s for the life of the episode.
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8080/health', timeout=3)"]
      interval: 3s
      timeout: 5s
      retries: 40
      start_period: 60s
"""

_MAIN_DOCKERFILE = """FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \\
    tmux git curl ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY team /usr/local/bin/team
RUN chmod +x /usr/local/bin/team
"""

#: A solve.sh that exits 0 having done nothing would claim the task is
#: solvable on no evidence. The in-process evidence that exists so far is the
#: OPEN control (output/rollouts/), which is the ablation twin, not the
#: shipped configuration -- so no solution is claimed here until a star
#: orchestration is demonstrated and recorded.
_SOLVE_NO_REFERENCE = """#!/bin/bash
# There is no demonstrated reference orchestration for this configuration.
# The OPEN control has been run and judged in-process (see output/rollouts/),
# which evidences the scenario is solvable -- but a control run is not a
# star orchestration, and this script will not claim one exists.
echo 'no reference orchestration recorded for this Gaia2 configuration' >&2
exit 1
"""


def write_task(
    scenario_path: str | Path,
    scenario_id: str,
    constraints: Constraints,
    out_dir: str | Path,
    token: str,
) -> Path:
    """Render one Harbor task. Returns its directory."""
    label = constraints.label
    task_dir = Path(out_dir) / f"gaia2-{label}-{scenario_id}"
    (task_dir / "environment").mkdir(parents=True, exist_ok=True)
    (task_dir / "tests").mkdir(parents=True, exist_ok=True)
    (task_dir / "solution").mkdir(parents=True, exist_ok=True)

    config = {
        "roster": list(constraints.roster),
        "topology": constraints.topology.value,
        "visibility": constraints.visibility.value,
        # Gaia2's bN is deliberately soft: the sidecar records an auxiliary
        # economy signal but never refuses delegation N+1.
        "delegation_target": constraints.delegation_budget,
    }

    (task_dir / "task.toml").write_text(_TASK_TOML.format(
        label=label, scenario_id=scenario_id,
        roster="+".join(constraints.roster),
        difficulty=_difficulty(constraints)))

    (task_dir / "instruction.md").write_text(render_instruction(constraints))

    env = task_dir / "environment"
    (env / "docker-compose.yaml").write_text(_COMPOSE.format(
        config_json=json.dumps(config), token=token))
    (env / "Dockerfile").write_text(_MAIN_DOCKERFILE)

    # The world itself. Byte-identical to the fetched scenario file, so a
    # reviewer can diff a shipped task against the dataset.
    (env / "scenario.json").write_text(Path(scenario_path).read_text())

    for dest, src in VERBATIM_COPIES.items():
        target = task_dir / dest
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(src.read_text())

    (task_dir / "tests" / "verifier_token.txt").write_text(token)
    (task_dir / "tests" / "test.sh").write_text(
        "#!/bin/bash\nmkdir -p /logs/verifier\npython3 /tests/verify.py\n")

    (task_dir / "solution" / "solve.sh").write_text(_SOLVE_NO_REFERENCE)

    os.chmod(task_dir / "tests" / "test.sh", 0o755)
    os.chmod(task_dir / "solution" / "solve.sh", 0o755)
    os.chmod(env / "team", 0o755)
    return task_dir


def render_instruction(c: Constraints) -> str:
    """The Main's brief: goal, roster, action surface -- never a procedure.

    Unlike AppWorld's, this brief does not embed the task text. The task
    arrives from the world (`team roster` shows the opening message, and
    later turns arrive as notifications), because a Gaia2 scenario is
    multi-turn and quoting the transcript up front would leak instructions
    the user has not sent yet.
    """
    if c.topology is Topology.CHAIN:
        routing = (
            f"You may delegate only to `{c.roster[0]}`. Specialists hand off down "
            f"the chain themselves: {' -> '.join(c.roster)}."
        )
    else:
        routing = "You may delegate to: " + ", ".join(f"`{r}`" for r in c.roster)

    know = (
        "You know their names only. You do not know what any of them can do."
        if c.visibility is Visibility.NAMES
        else "Each specialist's documentation is available via `team docs <name>`."
    )
    budget = (
        "" if c.delegation_budget is None
        else (
            f"\n- Your delegation-efficiency target is **{c.delegation_budget}**. "
            "It is not a hard cap: if more delegations are needed to complete "
            "the task, keep going. Going over lowers only the auxiliary economy "
            "signal."
        )
    )

    return f"""# gaia2 orchestration

You are the **Main agent**. You have **no API access of any kind**. You cannot
read or write any app. Every action must be performed by a specialist.

## Your task

Run `team roster`. Its `instruction` field is the user's request. This world
runs on a **simulated clock**: replies, confirmations and follow-ups arrive at
later simulated times, and `team wait` is how you let them.

## Objective action contract

Contract version: `{OBJECTIVE_ACTION_CONTRACT_VERSION}`.

{OBJECTIVE_ACTION_CONTRACT}

## Your team

{routing}
{know}

Each specialist can use only its own app, and none of them knows your task.

## Commands

- `team roster` — list your specialists and read the user's request.
- `team ask <specialist> "<request in plain English>"` — send a request and read
  the reply.
- `team wait <seconds>` — let simulated time pass until the next notification
  or the timeout, and read whatever arrived.
- `team done "<answer>"` — report to the user. Use `completed` if the task was
  an action rather than a question. If the reply says `continued`, the user has
  sent a follow-up: keep working.
- `team fail "<reason>"` — tell the user truthfully that you could not do it.
  Never claim completion you did not achieve; `fail` is the channel for it.

## What is scored

The actions taken in the apps while you worked, checked against what the task
asked for — including whether you changed anything you should not have, and
whether actions happened when they were supposed to. Not your reasoning, not
the number of messages you sent.{budget}
"""
