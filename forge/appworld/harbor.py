"""Render a selected AppWorld task + a constraint configuration into a Harbor task.

## Where the isolation boundary is, and why it is not negotiable

The Main is the model under test. If AppWorld lived in the Main's container, the
Main could import it, call `apis.venmo.*` directly, read the task's ground truth,
or run `evaluate()` -- and the whole constraint layer would be a suggestion. This
repo has already been burned by exactly that class of mistake: the previous
generation shipped the dimension module (generator, oracle, verifier) into the
agent's image, and because the generator was seed-deterministic an agent could
brute-force the seed and recover ground truth that supposedly lived in `/tests`.
Four such exploits were executed for real before they were closed.

So: AppWorld, the specialists, and the oracle live in a **sidecar**. The Main's
container gets a ~30-line HTTP client and nothing else. "The Main has no API
access" is then a property of the filesystem, not of a prompt.

Harbor 0.18 supports this natively -- `trial.py:842` discovers
`environment/docker-compose.yaml`, and `constants.py:26` puts the agent in the
`main` service. The verifier also runs in `main`, so it reaches the sidecar over
the compose network and authenticates with a token that is written to `tests/`
(uploaded only at verification time, per `verifier/verifier.py:147`) and passed
to the sidecar through its own compose `environment:` block. Neither path enters
the agent's image.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from forge.appworld.partition import Constraints, Topology, Visibility

_RUNTIME = Path(__file__).parent / "container"

_TASK_TOML = """schema_version = "1.3"
artifacts = []

[task]
name = "demo/appworld-{label}-{task_id}"
description = "Multi-agent orchestration over AppWorld ({roster}), {label}."
keywords = ["multi-agent", "rl", "orchestration", "appworld"]
[[task.authors]]
name = "multi-agent-task-forge"

[metadata]
difficulty = "{difficulty}"
category = "agentic"
tags = ["multi-agent", "orchestration", "appworld"]

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
      - maf-env

  maf-env:
    build:
      context: .
      dockerfile: Dockerfile.sidecar
    environment:
      MAF_TASK_ID: "{task_id}"
      MAF_CONFIG: '{config_json}'
      MAF_VERIFIER_TOKEN: "{token}"
      OPENAI_API_KEY: "${{OPENAI_API_KEY}}"
    expose:
      - "8079"
"""

_MAIN_DOCKERFILE = """FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \\
    tmux git curl ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY team /usr/local/bin/team
RUN chmod +x /usr/local/bin/team
"""


def _difficulty(c: Constraints) -> str:
    """Difficulty ladder, in the order the constraints actually bite.

    Nothing here is a guess about hardness: the knobs are ordered by how much
    they remove from the Main. Whether the ladder is real is decided by
    measurement (see scripts/appworld_knob_sweep.py), not by this function.
    """
    if c.topology is Topology.OPEN:
        return "easy"
    score = len(c.roster) - 2
    score += 1 if c.visibility is Visibility.NAMES else 0
    score += 1 if c.topology is Topology.CHAIN else 0
    score += 1 if c.delegation_budget is not None else 0
    return ("easy", "medium", "hard")[min(score, 2)]


def write_task(
    task_id: str,
    instruction: str,
    constraints: Constraints,
    out_dir: str | Path,
    token: str,
) -> Path:
    """Render one Harbor task. Returns its directory."""
    label = constraints.label
    task_dir = Path(out_dir) / f"appworld-{label}-{task_id}"
    (task_dir / "environment").mkdir(parents=True, exist_ok=True)
    (task_dir / "tests").mkdir(parents=True, exist_ok=True)
    (task_dir / "solution").mkdir(parents=True, exist_ok=True)

    config = {
        "task_id": task_id,
        "roster": list(constraints.roster),
        "topology": constraints.topology.value,
        "visibility": constraints.visibility.value,
        "delegation_budget": constraints.delegation_budget,
    }

    (task_dir / "task.toml").write_text(_TASK_TOML.format(
        label=label, task_id=task_id, roster="+".join(constraints.roster),
        difficulty=_difficulty(constraints)))

    (task_dir / "instruction.md").write_text(render_instruction(instruction, constraints))

    env = task_dir / "environment"
    (env / "docker-compose.yaml").write_text(_COMPOSE.format(
        task_id=task_id, config_json=json.dumps(config), token=token))
    (env / "Dockerfile").write_text(_MAIN_DOCKERFILE)
    (env / "Dockerfile.sidecar").write_text((_RUNTIME / "Dockerfile.sidecar").read_text())
    (env / "team").write_text((_RUNTIME / "team").read_text())
    (env / "server.py").write_text((_RUNTIME / "server.py").read_text())

    # The token lives in tests/, which Harbor uploads only at verification time,
    # so the agent phase never sees it. Without it the sidecar refuses /state.
    (task_dir / "tests" / "verifier_token.txt").write_text(token)
    (task_dir / "tests" / "verify.py").write_text((_RUNTIME / "verify.py").read_text())
    (task_dir / "tests" / "test.sh").write_text(
        "#!/bin/bash\nmkdir -p /logs/verifier\npython3 /tests/verify.py\n")

    (task_dir / "solution" / "solve.sh").write_text(
        "#!/bin/bash\n"
        "# No planted solution. The oracle is AppWorld's state check, and the\n"
        "# reference path is a real orchestration -- there is nothing to replay.\n"
        "echo 'appworld tasks have no planted oracle by design' >&2\nexit 1\n")

    os.chmod(task_dir / "tests" / "test.sh", 0o755)
    os.chmod(task_dir / "solution" / "solve.sh", 0o755)
    os.chmod(env / "team", 0o755)
    return task_dir


def render_instruction(instruction: str, c: Constraints) -> str:
    """The Main's brief.

    It states the goal, the roster, and the action surface. It never states a
    procedure -- no "ask phone first, then tell venmo". The dimension this
    project retired stated its own optimal algorithm in the instruction, and both
    models then scored `asks == q_opt` on 12 of 12 runs with zero gradient. The
    dictation gate exists because of that, and this text is what it checks.
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
        else f"\n- You may delegate at most **{c.delegation_budget}** times."
    )

    return f"""# appworld orchestration

You are the **Main agent**. You have **no API access of any kind**. You cannot
read or write any app. Every action must be performed by a specialist.

## Your task

{instruction}

## Your team

{routing}
{know}

Each specialist can use only its own app, and none of them knows your task.

## Commands

- `team roster` — list your specialists.
- `team ask <specialist> "<request in plain English>"` — send a request and read
  the reply.
- `team done "<answer>"` — finish. Use `completed` if the task was an action
  rather than a question.

## What is scored

The state of the apps when you finish, checked against what the task asked for —
including whether you changed anything you should not have. Not your reasoning,
not the number of messages you sent.{budget}
"""
