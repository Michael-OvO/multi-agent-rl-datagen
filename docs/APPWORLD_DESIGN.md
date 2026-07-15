# Multi-Agent RL Task Construction over AppWorld

**Status:** Current
**Date:** 2026-07-15

Every number in this document was measured in this repository. Where something is
unmeasured, it says so.

---

## 1. Research: which capabilities, and why these

The brief lists ten capabilities: theory of mind, collaboration topologies, task
decomposition and orchestration, dependency identification and parallel
scheduling, dynamic replanning and failure recovery, long-horizon planning, role
assignment, Main↔Sub / Sub↔Sub communication, role-awareness.

They do not divide by importance. They divide by **whether a free oracle exists**.

| | Capability | Who judges "done"? |
|---|---|---|
| **Coordination over a world** | dependency identification, parallel scheduling, replanning, failure recovery, long-horizon planning | the world executes → the oracle is free |
| **Coordination over other minds** | theory of mind, topologies, Main↔Sub / Sub↔Sub communication, role-awareness | the "other minds" must be simulated → **we** design the oracle |

This is not a taxonomy invented for the write-up. It is the retrospective on a
failure in this repository, and it is the single most useful thing we learned.

### 1.1 The failure mode that matters most is in the task, not the model

A previous generation of this forge shipped a `theory-of-mind` dimension. We
built the world *and* the judge. A flaw in the world's design became a flaw in
the reward:

- The instruction named each topic's entry witness and said to follow referrals.
- Following referrals costs exactly `q_opt`, the optimum.
- So **obeying the instruction literally was optimal play.**

Measured: gpt-5.6 and gpt-4.1 both scored `asks == q_opt` on **12 of 12** runs at
every difficulty. Reward 1.0 everywhere. Zero variance, therefore zero advantage,
therefore **zero gradient** — the data was worth nothing for RL, regardless of
how good it looked.

Every validity gate passed while this was true. The task measured
instruction-following and reported it as theory of mind.

An audit then found four working exploits against the same forge, each scoring
1.0, the worst being seed brute-force: the generator shipped inside the agent's
image and was seed-deterministic, so an agent could regenerate the instance and
read ground truth that supposedly lived in `/tests`. That broke every dimension,
including the one believed sound.

**The lesson generalises:** the dangerous failures were not in the policy. They
were in the parts of the task *we designed* — the oracle, the optimum, the
isolation. And they were **invisible**: everything was green.

### 1.2 Curriculum order falls out of the same split

World-coordination before mind-coordination. Not because it is conceptually
prior, but because its oracle is free and therefore its tasks can be trusted. A
mind-coordination task built before you can trust your own oracle is how you get
`asks == q_opt` on 12 of 12 runs and never notice.

### 1.3 What current models actually fail at, measured here

On AppWorld task `2a163ab_1` — *"Like all the venmo transactions from today
involving any of my roommates"* — with a `phone` specialist and a `venmo`
specialist available:

    [MAIN -> venmo] "List the usernames of my roommates on Venmo."
    [venmo -> MAIN] "ed_wilson, kri-powe, les_ball, tr_solo, ..."

Venmo has no address book. It substituted its **friends list** for "roommates"
and answered confidently. The true roommates — which the `phone` specialist
retrieves without difficulty — are Anthony Harrison, Anita Burch, Nicholas Weber:
a completely different set.

**The Main never queried `phone` at all.** It routed everything to the app that
owns the final action.

Two failure modes, both real, both on the first runs:
1. **The Main does not model what each specialist can possibly know.** It asks
   whoever performs the action, not whoever holds the fact.
2. **A specialist asked outside its competence guesses rather than declines** —
   and a confident wrong answer is worse than a refusal.

We did not design either. They fell out of the access constraint, and AppWorld's
oracle catches the consequence for free.

---

## 2. The construction method

### 2.1 The principle: manufacture constraints, inherit the judge

The retired dimension built the world and the judge, so a design flaw became a
reward flaw. **A constraint cannot do that.** It changes *who can do what*, never
*what counts as done*.

The consequence is the whole design:

> A badly chosen constraint makes a task too easy or too hard — **measurable**.
> A badly designed oracle makes the reward measure the wrong thing — **invisible**.
> We trade an invisible failure mode for a visible one.

### 2.2 Task source and batch generation

Substrate: **AppWorld** — 9 apps, 457 APIs, 732 tasks, a real executable
environment, `pip install appworld`.

What we take: the task, the ground truth, the oracle, the environment. **All of
it.** What we add: constraints on access, information, and communication.

**The roster comes from the task, never from us.** A task's specialists are the
apps its ground-truth solution actually touches. We never choose how many
sub-agents a task gets, and we never pad a task with one it does not need.

That rule is load-bearing, and it rejected two thirds of the corpus:

| filter | usable tasks |
|---|---|
| naive — count every app the GT touches | **147 / 147 (100%)** |
| strict — drop `supervisor.complete_task` | **51 / 147 (34%)** |

`supervisor` is called in all 147 tasks and **every call is `complete_task`** —
the submit channel. It carries no information between apps. Counting it as a
collaborator turns 96 single-app puzzles into "multi-agent" tasks that would
ship with a decorative second specialist, pass every check, and measure nothing.

Largest real cluster: `phone`+`venmo` (30 tasks), then `file_system`+`spotify`,
`phone`+`simple_note`, `phone`+`simple_note`+`venmo`.

Batch generation is **reconfiguration, not invention**: 51 tasks × constraint
configurations. Each config is a different task for the model and the same task
for the oracle.

### 2.3 Environment construction

We do not construct one. `docker pull` / `pip install`.

The only thing we build is the **boundary**. AppWorld, the specialists and the
oracle live in a compose sidecar; the Main's container holds a 60-line HTTP
client with three verbs (`roster`, `ask`, `done`) and nothing else.

Verified on a rendered task — the agent's image contains exactly one file:

```
files in agent image: ['environment/team']
violations: NONE
```

This is not fastidiousness. It is the direct lesson of the four executed
exploits: if AppWorld were in the Main's container, the Main could call
`apis.venmo.*` directly, read the ground truth, or run `evaluate()` — and the
constraint layer would be a suggestion. "The Main has no API access" must be a
property of the filesystem, not a sentence in a prompt.

Harbor 0.18 supports this natively (`trial.py:842` discovers
`environment/docker-compose.yaml`; `constants.py:26` puts the agent in `main`).
The verifier also runs in `main`, so it authenticates to the sidecar with a token
written to `tests/` — which Harbor uploads only at verification time
(`verifier/verifier.py:147`), so the agent phase can never read the score.

### 2.4 Verification

We do not design it. AppWorld's `evaluate()` is:
- **programmatic** — no LLM judge, no rubric
- **state-based** — it compares the apps' database state against the task's goal,
  which is the practice τ-bench, τ²-bench and AppWorld converged on, because
  multiple valid tool-call paths satisfy the same goal
- **side-effect aware** — it also fails an agent that reached the goal
  destructively

Verified end-to-end before any of this was built: a hand-written solution to
`82e2fac_1` reached `success=True`, 2 passes, 0 failures.

Reward is `passes / (passes + failures)` — a count of **AppWorld's own
per-requirement unit tests**, not a metric we invented. There is no `q_opt` here,
no planted optimum, **nothing we can get wrong**.

### 2.5 Difficulty control

Difficulty is the constraint layer's knobs. Each targets one listed capability.

| knob | targets | status |
|---|---|---|
| **access partition** (OPEN control / STAR) | decomposition, role assignment, role-awareness | **measured, large effect** |
| **visibility** (DOCS / NAMES) | role-awareness, capability discovery as a communication act | behavioural effect measured; score effect **unmeasured** (§4) |
| **topology** (STAR / CHAIN) | Sub↔Sub communication | **unmeasured** |
| **delegation budget** | planning over trial-and-error | **not shipped** — unmeasured |

A budget is a constraint on the world, never a term in the reward. The reward
stays AppWorld's terminal state check under every configuration.

**The ablation twin is free.** `OPEN` is the same task, the same oracle, the knob
off. Any configuration that cannot beat it never tested coordination.

### 2.6 Scale path, and the real bottleneck

| stage | cost |
|---|---|
| environment | free — 250+ prebuilt images exist; AppWorld is one `pip install` |
| oracle | free — `evaluate()` |
| task + ground truth | free — 732 tasks |
| **selection** | seconds — regex over ground truth, fully automated |
| **specialist LLM calls** | **the bottleneck** |

Measured: one partitioned rollout took **4.2 hours** (15,127s for 66 specialist
turns ≈ 229s/turn). Almost all of it was sleeping in 429 backoff against a 30k
TPM ceiling. That is an account limit rather than an inherent cost — but it is
the binding constraint on this dimension today, and it is what stands between 3
sample tasks and 400.

A second, subtler bottleneck: **only tasks whose OPEN control succeeds can
measure a knob** (§4.1). That filter cannot be derived by inspection; it needs
real rollouts. It is the same logic as the gradient gate — all-0 carries as
little signal as all-1.

---

## 3. Deliverables

- **Forging pipeline:** `forge/appworld/` — `select` (roster from the task),
  `partition` (the constraint layer), `runtime` (Main + specialists), `harbor`
  (packaging), `cli` (`measure` / `render`).
- **Harbor tasks:** `python -m forge.appworld.cli render --n 3`
- **Evidence:** `sweep/appworld_span.json` (all 147 measured),
  `sweep/appworld_knobs.json` (knob effects).

---

## 4. What is not established

### 4.1 The partition saturates, so the finer knobs are unmeasured

Task `2a163ab_1`, Main = gpt-5.6-sol, specialists = gpt-4.1:

| config | partial | delegations | specialist turns |
|---|---|---|---|
| `open-docs` (control) | **0.83** | 0 | 12 |
| `star-docs` | **0.17** | 3 | 39 |
| `star-names` | **0.17** | 6 | 66 |
| `chain-names` | **0.17** | 12 | 55 |

The partition works: 0.83 → 0.17 is a 0.66 drop from one knob. The sub-agents are
the dominant factor in the task's difficulty, which is what the anti-toy rule
demanded evidence of.

But **every partitioned config lands on the same floor**, so the finer knobs show
no score difference. What they do show is a clean monotone effect on *effort*:

    open -> star-docs -> star-names -> chain-names
    0        3            6             12          delegations

Each additional constraint **doubles** the Main's delegations while the outcome
stays flat. So the knobs are biting — this is not decoration — but at this model
tier the difficulty ladder is expressed as work, not as score.

By the stated rule — a knob that does not move the score is decoration — these
would be delete candidates. The honest reading is narrower: they are
**unmeasurable at this difficulty**, because the partition alone already put the
model on the floor. Telling "no effect" apart from "no headroom" needs an easier
task or a stronger Main. They ship flagged, not validated.

### 4.2 One task, one seed

The knob table above is a single task and a single seed. It is enough to show the
partition dominates; it is not enough to rank configurations.

### 4.3 The measurement instrument nearly lied, twice

Both worth stating, because both are the kind of error this project keeps making:

1. **Floor effect.** The first sweep ran gpt-4.1 as the Main. Control and
   partitioned runs all scored 0.17 — an apparent "the knob does nothing". The
   control was already failing. A knob's effect is unmeasurable when the control
   is on the floor.
2. **A silent harness bug producing the same number.** gpt-5.x rejects
   `temperature=0`. Every call 400'd, the sweep's `except` swallowed it, and rows
   still reported `partial=0.17` — the untouched world's score, *identical to the
   genuinely failing gpt-4.1 runs*. Only a mechanism-level field (`turns=0`)
   distinguished a harness bug from a real result.

Outcome-only logging cannot tell "the agent tried and failed" from "the agent
never ran". Rows now carry `ran`, and caught errors print instead of being
buried.

### 4.4 What this dimension does not cover

Theory of mind, topologies and Sub↔Sub communication are *pressured* by the
constraints — §1.3 shows the Main failing at exactly the ToM step — but nothing
here **isolates** them. A task where the Main fails could be failing at
decomposition, at briefing, or at modelling what venmo can know. Attributing the
failure needs per-capability probes this does not have.
