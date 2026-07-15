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
from forge.appworld.reference import Reference

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
      maf-env:
        # Wait for the sidecar to be READY, not merely started. AppWorld's world
        # takes seconds to load; a plain `depends_on` let the verifier fire
        # first and report "cannot reach the sidecar" on a task that was fine.
        condition: service_healthy

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
    healthcheck:
      # /health, not /roster: /roster executes the API catalog against the live
      # world, and this fires every 3s for the life of the episode.
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8079/health', timeout=3)"]
      interval: 3s
      timeout: 5s
      retries: 30
      start_period: 10s
"""

_MAIN_DOCKERFILE = """FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \\
    tmux git curl ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY team /usr/local/bin/team
RUN chmod +x /usr/local/bin/team
"""


#: Placeholders rather than `.format()`: the script body is dense with literal
#: braces (f-strings, dict literals, the `{prev}` marker) and escaping every one
#: of them is a bug waiting to happen.
_SOLVE_REFERENCE = '''#!/bin/bash
# The reference orchestration: the decomposition a competent Main would find.
#
# This is NOT a replay. The specialists are real LLMs and do the actual work;
# what is recorded here is only the part the Main is measured on -- noticing that
# `phone` holds a fact `venmo` needs, and carrying it across. Everything else is
# still done live.
#
# So this oracle is probabilistic, not deterministic: it needs OPENAI_API_KEY at
# verification time, it costs tokens, and a bad specialist turn can fail it. That
# is a real cost, and it buys the only thing an oracle is for -- evidence the
# task is solvable, so that a failing Main is failing at orchestration rather
# than fighting a broken harness. See forge/appworld/reference.py.
set -euo pipefail

python3 - <<'MAF_SOLVE_EOF'
import json
import subprocess
import sys

STEPS = __STEPS__
ANSWER = __ANSWER__


def team(*args):
    p = subprocess.run(["team", *args], capture_output=True, text=True)
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError:
        sys.exit(f"team {args[0]} returned no JSON: {p.stdout!r} {p.stderr!r}")


prev = ""
for step in STEPS:
    reply = team("ask", step["specialist"], step["brief"].replace("{prev}", prev))
    if "report" not in reply:
        sys.exit(f"{step['specialist']} failed: {reply}")
    prev = reply["report"]
    print(f"{step['specialist']}: {prev}", file=sys.stderr)

team("done", ANSWER)
MAF_SOLVE_EOF
'''

#: A solve.sh that exits 0 having done nothing would claim the task is solvable
#: on no evidence, which is worse than shipping no claim at all.
_SOLVE_NO_REFERENCE = """#!/bin/bash
# There is no reference orchestration recorded for this task, so no solution has
# been demonstrated for it. Add one to forge/appworld/reference.py.
echo 'no reference orchestration for this task -- see forge/appworld/reference.py' >&2
exit 1
"""


def _solve_script(reference: Reference | None) -> str:
    if reference is None:
        return _SOLVE_NO_REFERENCE
    steps = [{"specialist": s.specialist, "brief": s.brief} for s in reference.steps]
    return (_SOLVE_REFERENCE
            .replace("__STEPS__", json.dumps(steps, indent=4))
            .replace("__ANSWER__", json.dumps(reference.answer)))


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
    reference: Reference | None = None,
) -> Path:
    """Render one Harbor task. Returns its directory.

    `reference` is the orchestration the solution replays. Without one the task
    still renders, but its solve.sh fails loudly rather than claiming a solution
    nobody has demonstrated.
    """
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

    # The sidecar needs the specialist loop and the constraint definitions. They
    # go into the build context under their own directory, which only
    # Dockerfile.sidecar copies -- the agent's Dockerfile does not, so they never
    # reach the image the Main runs in. Plan 1's leak audit reads COPY
    # directives precisely so it can tell these two cases apart.
    pkg = env / "maf_appworld"
    pkg.mkdir(exist_ok=True)
    _pkg_src = Path(__file__).parent
    for mod in ("__init__.py", "partition.py", "runtime.py", "sandbox.py",
                "select.py"):
        (pkg / mod).write_text((_pkg_src / mod).read_text())

    # The token lives in tests/, which Harbor uploads only at verification time,
    # so the agent phase never sees it. Without it the sidecar refuses /state.
    (task_dir / "tests" / "verifier_token.txt").write_text(token)
    (task_dir / "tests" / "verify.py").write_text((_RUNTIME / "verify.py").read_text())
    (task_dir / "tests" / "test.sh").write_text(
        "#!/bin/bash\nmkdir -p /logs/verifier\npython3 /tests/verify.py\n")

    (task_dir / "solution" / "solve.sh").write_text(_solve_script(reference))

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
