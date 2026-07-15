# Multi-Agent Foundational-Capability RL Data Generation

A scalable pipeline (`forge`) that generates **verifiable RL training tasks** for
multi-agent **orchestration** capabilities, packaged in [Harbor](https://www.harborframework.com)
format, plus three oracle-verified sample tasks and a reusable task-forging skill.

## The idea in one paragraph

Multi-agent capabilities normally live in *live* multi-agent systems, which are
non-deterministic, expensive, and hard to grade — the opposite of what RL needs.
We **invert the setup**: the model under test plays the single **orchestrator
(Main agent)** role, while every other agent and the world are a **deterministic
scripted environment that holds ground truth**. The environment *is* the verifier,
so reward is programmatic, reproducible, continuous (`[0,1]`), and cheap. Each
capability is a **parametric environment family** sampled by `generate(seed,
difficulty)`, so tasks scale procedurally — each auto-gated by a **CLEAN/VALID**
battery before it ships.

Full design + validity argument: [`docs/DESIGN.md`](docs/DESIGN.md).
Verification evidence: [`docs/RESULTS.md`](docs/RESULTS.md).

## The three skills / tasks

| Task | Skill trained | Paradigm |
|---|---|---|
| `parallel-scheduling` | dependency identification + parallel scheduling | static, single-shot artifact |
| `failure-recovery` | dynamic replanning + failure recovery | interactive, multi-turn CLI |
| `theory-of-mind` | theory of mind + information-asymmetric communication | interactive, multi-turn CLI |

Each ships with an oracle that scores **1.0**, a **cheater panel** of shortcut
policies that provably lose, and an **ablation twin** proving the reward gap is
*caused by* the target skill (see `docs/DESIGN.md` §4.3).

## Layout

```
docs/DESIGN.md                    design doc (research + method + validity argument)
docs/RESULTS.md                   verification evidence
forge/maf/core.py                 reward shape + Dimension contract
forge/maf/dimensions/*.py         the three capability generators
forge/maf/selfcheck.py            the CLEAN/VALID gate battery
forge/maf/harbor.py               renders a Dimension+instance -> Harbor task dir
forge/maf/runtime/                generic in-container CLI + verifier (copied into tasks)
forge/forge_cli.py                `forge gen` — generate + gate + write
forge/tests/                      41 in-process tests (no Docker)
tasks/                            3 generated, oracle-verified sample tasks
scripts/verify_all.sh             real Harbor oracle run (needs Docker)
scripts/dryrun_local.py           oracle->verify logic check (no Docker)
skills/multi-agent-task-forge/    the reusable task-forging skill
```

## Quickstart

```bash
uv venv && uv sync                      # dev env (Python 3.11+)
uv run pytest forge/tests -q            # 41 tests, all in-process (no Docker)

# generate more tasks (each passes the CLEAN/VALID gate before it is written)
uv run python -m forge.forge_cli gen --dim parallel-scheduling \
    --seed 0 --n 20 --difficulty medium --out tasks/

python3 scripts/dryrun_local.py         # confirm oracle=1.0 without Docker
bash scripts/verify_all.sh              # confirm oracle=1.0 in real Harbor (Docker)
```

## Verify a single task in Harbor

```bash
uv tool install harbor                  # Harbor 0.18+

# reference solution (no API key needed) -> reward 1.0
harbor run --path tasks/parallel-scheduling-0003 --agent oracle -n 1

# a real LLM agent (any litellm provider; put the key in a gitignored .env)
harbor run --path tasks/parallel-scheduling-0003 \
    --agent terminus-2 --model openai/gpt-5.6 -n 1 --env-file .env
```

Measured with `gpt-5.6`: scheduling 1.00, theory-of-mind 1.00, failure-recovery
**0.75** (a real partial reward) — see [`docs/RESULTS.md`](docs/RESULTS.md).

## Adding a new capability dimension

Follow `skills/multi-agent-task-forge/SKILL.md`: name the skill and its shortcuts,
build an environment where each shortcut provably loses, write a **constructive**
generator (plant instance + optimal solution), a cheater panel, and an ablation
twin — then confirm `selfcheck` passes across ≥20 seeds.
