# Multi-Agent Foundational-Capability RL Data Generation

A forge that turns [AppWorld](https://appworld.dev)'s single-agent tasks into
multi-agent orchestration tasks by **constraining the agent's access to the
world, and never touching the judge** — packaged in
[Harbor](https://www.harborframework.com) format.

**Start here:** [`WRITEUP.md`](WRITEUP.md) — what was built, what was measured,
and what it turned out to measure.

## The idea in one paragraph

Multi-agent capability data has no free oracle: judging coordination means
simulating the other agents, and then **you** design the reward — which is exactly
how this repo's first attempt produced a `theory-of-mind` dimension that scored
1.0 on 12 of 12 runs while measuring instruction-following. So this forge does not
build tasks, environments, or verifiers. It takes AppWorld — 9 real apps, 457
APIs, 732 tasks, and a programmatic state-based oracle with no LLM in it — and
**constrains the agent's access to it**: the Main gets zero APIs and can only
delegate to app-specialist sub-agents, each bound to one app and blind to the
task. The task, the ground truth, the environment and the judge are all
AppWorld's, untouched.

> A badly chosen constraint makes a task too easy or too hard — **measurable**.
> A badly designed oracle makes the reward measure the wrong thing — **invisible**.

## The headline

Three tasks, one seed each, Main = gpt-5.6-sol, specialists = gpt-4.1.
`sweep/appworld_knobs_v3.json`. Floor (do nothing) = 0.333.

| config | mean | |
|---|---|---|
| `open` — one agent, every API | **1.000** | the control |
| `star-docs` — no APIs, may read its specialists' docs | **0.944** | the partition costs ~nothing |
| `star-names` — no APIs, does not know what they can do | **0.778** | *this* is what costs |
| `chain-names` | 0.333 | unshipped: scores the step cap, not the topology |

**Taking a frontier model's tools away and making it delegate did not make the
task hard — it made it longer.** Four of six partitioned rollouts still scored the
ceiling. The knob that bites is not *having* to delegate, it is **not knowing who
to delegate to**.

This repo previously reported `1.000 → 0.333` for the partition. That number was a
truncated API catalog hiding the verb the task needed — the specialists could not
find `like_transaction`, so they could not act, so the Main scored the floor no
matter how well it coordinated. [`WRITEUP.md`](WRITEUP.md) §7 is that story;
the numbers above are the re-measurement.

**What this is:** a working forge, 6 rendered Harbor tasks, 3 with verified
passing solutions, and an honest and unfinished measurement.
**What it is not:** a demonstrated curriculum. Three tasks at one seed cannot
price a 0.056 effect. The next run is seeds, not scale.

## Layout

| | |
|---|---|
| `forge/appworld/` | the pipeline: `select` (roster from the task) · `partition` (constraints) · `runtime` (Main + specialists) · `sandbox` (what specialist code may touch) · `reference` (the solutions) · `harbor` (packaging) · `cli` |
| `forge/maf/` | the earlier from-scratch forge; `parallel-scheduling` ships, two dimensions are quarantined (below) |
| `tasks/` | rendered Harbor tasks |
| `sweep/` | measurement evidence — one file per claim |
| `scripts/` | the probes that produced it |
| `skills/` | the method, and the failure modes it was built from |

Every number in the write-up names the file that produced it:

| evidence | question |
|---|---|
| `appworld_knobs_v3.json` | does each knob move the score against the control? |
| `appworld_donothing.json` | where is the floor? |
| `appworld_api_catalog.json` | what did truncating the API catalog destroy? |
| `appworld_injection.json` | can a brief make a specialist leak the reward token? |
| `appworld_oracle.json` | do the shipped solutions actually pass? |
| `appworld_span.json` | which of AppWorld's 147 tasks can carry a partition? |

## Quickstart

```bash
pip install appworld && appworld install && appworld download data

# which of AppWorld's tasks are genuinely multi-app (we never choose the roster)
python -m forge.appworld.cli measure --out sweep/appworld_span.json

# render Harbor tasks: 3 AppWorld tasks x 2 shipped configurations
python -m forge.appworld.cli render --n 3 --out tasks

# run one with a real model
harbor run --path tasks/appworld-star-names-binf-2a163ab_1 \
    --agent terminus-2 --model openai/gpt-5.6-sol -n 1 --env-file .env
```

Every AppWorld task ships a reference solution, verified end-to-end:

```bash
harbor run --path tasks/appworld-star-docs-binf-2a163ab_1 \
    --agent oracle -n 1 --env-file .env          # success=True, reward 1.0
```

That oracle is **probabilistic**: it replays the decomposition a competent Main
would find, but the specialists are real LLMs doing the real work, so it needs
`OPENAI_API_KEY` at verification time and costs tokens.

The earlier dimension still ships:

```bash
harbor run --path tasks/parallel-scheduling-0003 --agent oracle -n 1   # reward 1.0
```

## Two dimensions are quarantined, on purpose

`theory-of-mind` and `failure-recovery` are pinned at reward 0 in
`forge/tests/test_adversarial.py` and marked `xfail`. They are kept, not deleted,
because the write-up's argument is built on them: they are what a green dashboard
looks like when it is measuring nothing.

## Tests

```bash
python -m pytest        # the count is whatever the command prints
```

The two xfails are deliberate: the quarantined dimensions failing their gate — the
gate working, not a defect.
