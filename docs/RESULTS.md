# Verification Results

> **2026-07-14:** `theory-of-mind` and `failure-recovery` existed as sample
> dimensions and were quarantined — their CLI leaked ground truth into the
> agent's container image, and both reward constructs turned out to be
> degenerate. A later plan ports them to a sidecar; see `docs/RESEARCH.md`
> §3–4 for the rationale. No numbers for them appear below.

The `parallel-scheduling` sample task was verified end-to-end. Two things are
demonstrated:

1. **The task runs in real Harbor/Docker and the oracle scores 1.0** (correctness
   of environment + verifier + reference solution).
2. **The reward discriminates skill** — a spread from 0.0 (shortcut baselines) to
   1.0 (optimal play), which is the signal RL trains on.

## 1. Harbor oracle verification (real Docker)

Command: `harbor run --path <task> --agent oracle -n 1` (Harbor 0.18, Docker 28.4).

| Task | Trials | Exceptions | Reward | Runtime |
|---|---|---|---|---|
| `parallel-scheduling-0003` | 1 | 0 | **1.000** | 31s |

Reproduce: `bash scripts/verify_all.sh` (needs Docker). Logic-only (no Docker):
`python3 scripts/dryrun_local.py`.

## 2. Reward spread — the RL signal

The **CLEAN/VALID** gate guarantees `oracle − max(cheater) > 0.4`. Measured on the
shipped sample instance:

| Task | Oracle | Shortcut (cheater) rewards |
|---|---|---|
| `parallel-scheduling` | **1.00** | serial 0.42 · greedy-earliest 0.50 |

## 3. Real agent run — `terminus-2` + OpenAI `gpt-5.6` (in-container, via Harbor)

A live LLM agent, driven by Harbor inside the Docker container, on the shipped
task. (The task uses `network_mode = "public"` + tmux pre-installed so a
terminal agent can reach its model API; the oracle result above is unchanged.)

Command: `harbor run --path <task> --agent terminus-2 --model openai/gpt-5.6 -n 1 --env-file .env`

| Task | Reward | Read |
|---|---|---|
| `parallel-scheduling` | **1.00** | Found an optimal-makespan parallel schedule. |

No exceptions during the run.

## Takeaway

The environment, verifier, and reference solutions are correct (oracle 1.0 in real
Harbor), and the reward is a **graded, skill-discriminating signal** — exactly what
is needed to drive RL, produced deterministically with no LLM in the reward loop.
