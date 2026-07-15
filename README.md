# Multi-Agent Foundational-Capability RL Data Generation

A forge that produces **verifiable RL training tasks** for multi-agent
orchestration, packaged in [Harbor](https://www.harborframework.com) format.

**Start here:** [`WRITEUP.md`](WRITEUP.md) — what was built, what was measured,
and what was wrong.
Design detail: [`docs/DESIGN.md`](docs/DESIGN.md).

## The idea in one paragraph

Multi-agent capability data has no free oracle: judging coordination means
simulating the other agents, and then **you** design the reward — which is exactly
how this repo's first attempt produced a `theory-of-mind` dimension that scored
1.0 on 12 of 12 runs while measuring instruction-following. So this forge does not
build tasks, environments, or verifiers. It takes [AppWorld](https://appworld.dev)
— 9 real apps, 457 APIs, 732 tasks, and a programmatic state-based oracle with no
LLM in it — and **constrains the agent's access to it**: the Main gets zero APIs
and can only delegate to app-specialist sub-agents, each bound to one app and
blind to the task. The task, the ground truth, the environment and the judge are
all AppWorld's, untouched.

> A badly chosen constraint makes a task too easy or too hard — **measurable**.
> A badly designed oracle makes the reward measure the wrong thing — **invisible**.

## Layout

| | |
|---|---|
| `forge/appworld/` | the pipeline: `select` (roster from the task), `partition` (constraints), `runtime` (Main + specialists), `harbor` (packaging), `cli` |
| `forge/maf/` | the earlier from-scratch forge; `parallel-scheduling` ships, two dimensions are quarantined (below) |
| `tasks/` | rendered Harbor tasks |
| `sweep/` | measurement evidence (`appworld_span.json`, `appworld_knobs.json`) |
| `scripts/appworld_knob_sweep.py` | the anti-toy gate: does each knob actually move the score? |
| `docs/superpowers/specs/` | audit trail — the exploits, the retired dimensions, the deferred architecture |

## Quickstart

```bash
pip install appworld && appworld install && appworld download data

# measure every AppWorld task's task-determined roster (we never choose it)
python -m forge.appworld.cli measure --out sweep/appworld_span.json

# render Harbor tasks
python -m forge.appworld.cli render --n 2 --out tasks

# run one with a real model
harbor run --path tasks/appworld-star-names-binf-2a163ab_1 \
    --agent terminus-2 --model openai/gpt-5.6-sol -n 1 --env-file .env
```

The earlier dimension still ships and is verified end-to-end:

```bash
harbor run --path tasks/parallel-scheduling-0003 --agent oracle -n 1   # reward 1.0
```

## Headline measurements

All produced in this repo. Main = gpt-5.6-sol, specialists = gpt-4.1.

| | |
|---|---|
| Tasks that can carry a partition | **51 / 147** — counting the submit channel as a collaborator would claim 147/147 |
| **Partition effect** | **1.000 → 0.333** — the control solves the task completely; the partitioned Main gets a third of the way |
| Confound check (specialists upgraded to the control's model) | **unchanged** — the drop is the partition, not the weaker specialist |
| Model gradient on the control | gpt-4.1 **0.17** vs gpt-5.6-sol **1.000** |
| Agent image contents | exactly one file (`team`); leak audit: 0 violations |
| Cost | one partitioned rollout ≈ **4.2h**, almost all of it 429 backoff |

`open` is the **control**, not a deliverable: the same task and the same oracle
with the partition turned off, so that 0.333 can be read as *"hard"* rather than
*"impossible"*. Every shipped task is partitioned.

Not established, and stated as such in the write-up: the partition dominates, so
the finer knobs are unmeasured; `chain` is unimplemented and unshipped; two tasks
at one seed post-fix. For two days a harness bug capped every action task at
0.833 — that story is in [`WRITEUP.md`](WRITEUP.md) §5.3.

## Two dimensions are quarantined, on purpose

`theory-of-mind` and `failure-recovery` do not ship. Both leaked ground truth into
the agent's image, and both stated their own optimal algorithm in the
instruction. `forge/forge_cli.py` refuses to render them, and gate V4 rejects them
independently. Their constructs and the sidecar architecture that would fix them
are recorded in
[`docs/superpowers/specs/2026-07-15-deferred-dimensions-architecture.md`](docs/superpowers/specs/2026-07-15-deferred-dimensions-architecture.md).

Four exploits were executed against the earlier forge, each scoring 1.0 — the
worst being seed brute-force against a generator that shipped inside the agent's
own image. They are pinned at reward 0 in `forge/tests/test_adversarial.py`.

## Tests

```bash
python -m pytest        # 118 passed, 2 xfailed
```

The two xfails are deliberate: they are the quarantined dimensions failing gate
V4 — the gate working, not a defect.
