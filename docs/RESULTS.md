# Verification Results

All three sample tasks were verified end-to-end. Two things are demonstrated:

1. **The tasks run in real Harbor/Docker and the oracle scores 1.0** (correctness
   of environment + verifier + reference solution).
2. **The reward discriminates skill** — a spread from 0.0 (shortcut baselines) to
   1.0 (optimal play), which is the signal RL trains on.

## 1. Harbor oracle verification (real Docker)

Command: `harbor run --path <task> --agent oracle -n 1` (Harbor 0.18, Docker 28.4).

| Task | Trials | Exceptions | Reward | Runtime |
|---|---|---|---|---|
| `parallel-scheduling-0003` | 1 | 0 | **1.000** | 31s |
| `failure-recovery-0001` | 1 | 0 | **1.000** | 17s |
| `theory-of-mind-0002` | 1 | 0 | **1.000** | 17s |

Reproduce: `bash scripts/verify_all.sh` (needs Docker). Logic-only (no Docker):
`python3 scripts/dryrun_local.py`.

## 2. Reward spread — the RL signal

The **CLEAN/VALID** gate guarantees `oracle − max(cheater) > 0.4`. Measured on the
shipped sample instances:

| Task | Oracle | Shortcut (cheater) rewards |
|---|---|---|
| `parallel-scheduling` | **1.00** | serial 0.42 · greedy-earliest 0.50 |
| `failure-recovery` | **1.00** | static-plan 0.00 · retry-same 0.00 · brute-force 0.00 |
| `theory-of-mind` | **1.00** | info-dump 0.50 · random-target 0.50 · no-referral 0.00 |

Note the theory-of-mind row: info-dump and random-target *found the correct
culprit* yet still score 0.50 — the query budget caps `quality = q_opt/used ≤ 0.5`
for any policy that spends its whole budget. Info-dumping is punished even when
lucky; only referral-following reaches 1.0.

## 3. Real agent run — `terminus-2` + OpenAI `gpt-5.6` (in-container, via Harbor)

A live LLM agent, driven by Harbor inside the Docker container, on the three
shipped tasks. (Tasks use `network_mode = "public"` + tmux pre-installed so a
terminal agent can reach its model API; the oracle result above is unchanged.)

Command: `harbor run --path <task> --agent terminus-2 --model openai/gpt-5.6 -n 1 --env-file .env`

| Task | Reward | Read |
|---|---|---|
| `parallel-scheduling` | **1.00** | Found an optimal-makespan parallel schedule. |
| `theory-of-mind` | **1.00** | Followed the referral chains to the clue-holders and named the culprit within budget. |
| `failure-recovery` | **0.75** | **Genuine partial reward** — completed every subtask but used all 8 dispatches (`quality = d_opt/used = 6/8`), wasting 2 attempts recovering from decoys. |

The `0.75` is the headline: a frontier model lands **between** the shortcut
baselines (0.0) and the optimum (1.0) — the reward is a real gradient that tracks
*how well* the skill was exercised, not a pass/fail. 0 exceptions across all runs.

### 3b. Cross-check — Claude Code played fresh instances by hand

As an independent check (before the OpenAI run), Claude Code played **fresh**
instances (unseen seeds) through the public CLI only, no ground-truth peeking:
`theory-of-mind` (seed 91) → **1.00** (optimal referral-following); `failure-recovery`
(seed 88) → **0.00** (dispatched before dependencies were ready and mis-inferred a
worker, exhausting the budget). Same conclusion from a different model: the reward
discriminates real skill.

## Takeaway

The environment, verifier, and reference solutions are correct (oracle 1.0 in real
Harbor), and the reward is a **graded, skill-discriminating signal** — exactly what
is needed to drive RL, produced deterministically with no LLM in the reward loop.
