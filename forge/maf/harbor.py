"""Render a Dimension + instance into a runnable Harbor 0.18 task directory.

Single source of truth: the dimension's Python module is *copied* (with its one
internal import rewritten) into ``tests/lib/``, which Harbor uploads only at
verification time -- after the agent phase completes. The in-container
verifier therefore grades with exactly the code the selfcheck battery
validated, without ever shipping that code (``generate``/``ORACLE``/``verify``/
``CHEATERS``) to a place the agent can read it.
"""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path

from forge.maf.core import public

_RUNTIME = Path(__file__).parent / "runtime"

# Shared image base. tmux/git/curl are pre-installed at BUILD time (build always
# has network) so terminal agents like terminus-2 work without runtime installs.
_DOCKER_BASE = (
    "FROM python:3.11-slim\n"
    "RUN apt-get update && apt-get install -y --no-install-recommends "
    "tmux git curl ca-certificates && rm -rf /var/lib/apt/lists/*\n"
    "WORKDIR /app\n"
)


def write_task(dim, instance: dict, out_dir, task_id: str) -> Path:
    task_dir = Path(out_dir) / f"{dim.NAME}-{task_id}"
    for sub in ("environment", "tests/lib", "solution"):
        (task_dir / sub).mkdir(parents=True, exist_ok=True)

    # The dimension module holds generate()/ORACLE/verify()/CHEATERS. It ships to
    # tests/, which Harbor uploads only at verification time -- never to the
    # agent's image. See docs/DESIGN.md §5.
    _copy_runtime(dim, task_dir / "tests" / "lib", include_cli=dim.INTERACTIVE)
    (task_dir / "task.toml").write_text(_task_toml(dim, task_id))
    (task_dir / "instruction.md").write_text(_instruction(dim, instance))
    (task_dir / "tests" / "verify.py").write_text(
        (_RUNTIME / "verify_entry.py").read_text()
    )
    (task_dir / "tests" / "test.sh").write_text(_TEST_SH)

    pub = public(instance)
    gt = {k: v for k, v in instance.items() if k.startswith("_")}

    if not dim.INTERACTIVE:
        cfg = _write_static(dim, instance, pub, gt, task_dir)
    else:
        cfg = _write_interactive(dim, instance, pub, gt, task_dir)

    (task_dir / "tests" / "verify_config.json").write_text(json.dumps(cfg, indent=2))
    os.chmod(task_dir / "solution" / "solve.sh", 0o755)
    os.chmod(task_dir / "tests" / "test.sh", 0o755)
    return task_dir


# --------------------------------------------------------------------------- #
# Static dimensions (single-shot artifact, e.g. scheduling)
# --------------------------------------------------------------------------- #
def _write_static(dim, instance, pub, gt, task_dir) -> dict:
    (task_dir / "environment" / "task.json").write_text(json.dumps(pub, indent=2))
    (task_dir / "tests" / "ground_truth.json").write_text(json.dumps(gt))
    (task_dir / "environment" / "Dockerfile").write_text(
        _DOCKER_BASE + "COPY task.json /app/task.json\n"
    )
    planted = json.dumps(dim.run_policy(instance, dim.ORACLE))
    (task_dir / "solution" / "solve.sh").write_text(
        "#!/bin/bash\nset -e\n"
        f"cat > /app/{dim.SUBMISSION_FILE} <<'MAF_EOF'\n{planted}\nMAF_EOF\n"
    )
    return {
        "interactive": False,
        "scenario_path": "/app/task.json",
        "ground_truth_path": "/tests/ground_truth.json",
        "submission_path": f"/app/{dim.SUBMISSION_FILE}",
    }


# --------------------------------------------------------------------------- #
# Interactive dimensions — completed in Task 6 (needs runtime/cli.py)
# --------------------------------------------------------------------------- #
def _write_interactive(dim, instance, pub, gt, task_dir) -> dict:
    # Full scenario (incl. ground-truth `_` fields) lives at /opt/maf, outside the
    # agent's /app workdir. The CLI reads it; the agent uses only the CLI.
    (task_dir / "environment" / "scenario.json").write_text(json.dumps(instance, indent=2))
    cli = dim.CLI_NAME
    (task_dir / "environment" / cli).write_text(
        '#!/bin/bash\nexec python3 /app/lib/cli.py "$@"\n'
    )
    (task_dir / "environment" / "Dockerfile").write_text(
        _DOCKER_BASE
        + "COPY lib /app/lib\n"
        "RUN mkdir -p /opt/maf\n"
        "COPY scenario.json /opt/maf/scenario.json\n"
        f"COPY {cli} /usr/local/bin/{cli}\n"
        f"RUN chmod +x /usr/local/bin/{cli}\n"
    )
    (task_dir / "solution" / "solve.sh").write_text(
        "#!/bin/bash\nset -e\n"
        "python3 - <<'PY'\n"
        "import json, sys\n"
        "sys.path.insert(0, '/app/lib')\n"
        "import maf_dim\n"
        "inst = json.load(open('/opt/maf/scenario.json'))\n"
        "tr = maf_dim.run_policy(inst, maf_dim.ORACLE)\n"
        "with open('/app/transcript.jsonl', 'w') as fh:\n"
        "    for x in tr:\n"
        "        fh.write(json.dumps(x) + '\\n')\n"
        "PY\n"
    )
    return {
        "interactive": True,
        "scenario_path": "/opt/maf/scenario.json",
        "ground_truth_path": None,
        "submission_path": "/app/transcript.jsonl",
    }


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _copy_runtime(dim, lib_dir: Path, include_cli: bool = False):
    import forge.maf.core as core_mod

    lib_dir.mkdir(parents=True, exist_ok=True)
    lib_dir.joinpath("maf_core.py").write_text(Path(core_mod.__file__).read_text())
    mod = importlib.import_module(type(dim).__module__)
    src = Path(mod.__file__).read_text()
    src = src.replace("from forge.maf.core import", "from maf_core import")
    lib_dir.joinpath("maf_dim.py").write_text(src)
    if include_cli:
        lib_dir.joinpath("cli.py").write_text((_RUNTIME / "cli.py").read_text())


def _instruction(dim, instance) -> str:
    return (
        f"# {dim.NAME}\n\n{dim.GOAL}\n\n"
        f"{dim.render_instruction(instance)}\n\n"
        f"## Output contract\n\n{dim.OUTPUT_CONTRACT}\n"
    )


def _task_toml(dim, task_id: str) -> str:
    return (
        'schema_version = "1.3"\n'
        "artifacts = []\n\n"
        "[task]\n"
        f'name = "demo/{dim.NAME}-{task_id}"\n'
        f'description = "Multi-agent {dim.NAME} RL task (forge-generated)."\n'
        f'keywords = ["multi-agent", "rl", "{dim.NAME}"]\n'
        "[[task.authors]]\n"
        'name = "multi-agent-task-forge"\n\n'
        "[metadata]\n"
        'difficulty = "medium"\n'
        'category = "agentic"\n'
        'tags = ["multi-agent", "orchestration"]\n\n'
        "[verifier]\n"
        "timeout_sec = 300.0\n"
        "collect = []\n\n"
        "[verifier.env]\n\n"
        "[agent]\n"
        "timeout_sec = 600.0\n\n"
        "[environment]\n"
        # "public" lets terminal agents (terminus-2, etc.) reach their model API.
        # These tasks are self-contained — nothing on the internet helps solve them —
        # so egress does not enable cheating.
        'network_mode = "public"\n'
        "build_timeout_sec = 600.0\n"
        'os = "linux"\n'
        "mcp_servers = []\n\n"
        "[environment.env]\n\n"
        "[solution.env]\n"
    )


_TEST_SH = "#!/bin/bash\nmkdir -p /logs/verifier\npython3 /tests/verify.py\n"
