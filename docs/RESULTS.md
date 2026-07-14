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

## 3. Live agent trajectories (Claude Code as the agent)

`ANTHROPIC_API_KEY` was not available for an in-container `claude-code` run, so
the model played **fresh** instances (seeds it had not inspected) honestly through
the public CLI — no ground-truth peeking. These are genuine non-oracle rollouts.

| Task (fresh seed) | Reward | What happened |
|---|---|---|
| `failure-recovery` (seed 88) | **0.00** | Speculatively dispatched t1/t2 before their dependency t0 completed (2 wasted ERROR dispatches), then failed to try the one good worker for t1 — ran out of budget with t1 incomplete. A real, instructive failure: the task punishes both dependency violations and inefficient recovery. |
| `theory-of-mind` (seed 91) | **1.00** | Followed every referral chain (entry → mid → knower `a6`), gathered all 4 clues in exactly `q_opt`=12 questions, deduced the sole remaining suspect `s1`, submitted correctly. |

The contrast (0.00 vs 1.00 on comparable difficulty) is the point: the reward is
not trivially achievable — it tracks whether the agent actually exercised the
target skill.

## Takeaway

The environment, verifier, and reference solutions are correct (oracle 1.0 in real
Harbor), and the reward is a **graded, skill-discriminating signal** — exactly what
is needed to drive RL, produced deterministically with no LLM in the reward loop.
