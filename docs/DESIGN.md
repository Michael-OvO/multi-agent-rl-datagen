# Multi-Agent Foundational-Capability RL Data Generation — Design

**Status:** Current
**Date:** 2026-07-15

Every number here was measured in this repository. Where something is unmeasured
or wrong, it says so. The story of how this design was arrived at — including the
version that failed — is in [`../WRITEUP.md`](../WRITEUP.md).

---

## 0. TL;DR

Multi-agent capability data has no free oracle: judging coordination means
simulating the other agents, and then **you** design the reward. This repo's first
version did exactly that and produced a `theory-of-mind` dimension that scored
1.0 on 12 of 12 runs while measuring instruction-following (§6).

So this forge builds no tasks, no environments, and no verifiers. It **mines**
[AppWorld](https://appworld.dev) — 9 real apps, 457 APIs, 732 tasks, and a
programmatic state-based oracle with no LLM in it — **measures** which of its
tasks are genuinely multi-app, and **constrains** the agent's access to them: the
Main gets zero APIs and can only delegate to app-specialist sub-agents, each bound
to one app and blind to the task.

> A badly chosen constraint makes a task too easy or too hard — **measurable**.
> A badly designed oracle makes the reward measure the wrong thing — **invisible**.
> Trade the invisible failure mode for the visible one.

---

## 1. Research: which capabilities, and why these

The brief lists ten: theory of mind, collaboration topologies, task decomposition
and orchestration, dependency identification and parallel scheduling, dynamic
replanning and failure recovery, long-horizon planning, role assignment,
Main↔Sub / Sub↔Sub communication, role-awareness.

They do not divide by importance. They divide by **whether a free oracle exists**.

| | capabilities | who judges "done"? |
|---|---|---|
| **Coordination over a world** | dependency identification, parallel scheduling, replanning, failure recovery, long-horizon planning | the world executes → **the oracle is free** |
| **Coordination over other minds** | theory of mind, topologies, Main↔Sub / Sub↔Sub communication, role-awareness | the minds must be simulated → **we** design the oracle |

This is not a taxonomy invented for a write-up. It is the retrospective on §6:
`parallel-scheduling` survived an audit; `theory-of-mind` died. Scheduling's
oracle re-executes the submitted artifact. Theory-of-mind's oracle was a number
we computed, and computed wrong.

### 1.1 Curriculum order falls out of the same split

**World-coordination before mind-coordination** — not because it is conceptually
prior, but because its oracle can be trusted. Building a mind-coordination task
before you can trust your own oracle is how you get 12/12 at 1.0 and never
notice.

### 1.2 The state of the field (checked, not assumed)

There is **no multi-agent trace + environment + free-oracle corpus.** The
[orchestration-traces survey](https://arxiv.org/html/2605.02801v1) states that
causal credit "is not identifiable from realized on-policy traces alone" and
ships a JSON schema rather than a dataset.
[MultiAgentBench](https://arxiv.org/abs/2503.01935) has star/chain/tree
topologies but scores with milestone KPIs. So everyone must manufacture the
multi-agent structure; the only question is **which layer** — and the layer we
choose cannot reach the judge.

Supporting practice: [τ-bench and AppWorld](https://arxiv.org/pdf/2602.16246)
converged on **terminal-state** evaluation rather than trajectory matching,
because multiple valid tool-call paths satisfy the same goal.
[Best practices for agentic benchmarks](https://arxiv.org/pdf/2507.02825) names
grader-code isolation and outcome validity — and reports that multiple published
benchmarks fail both, which is where §6's exploits came from.

### 1.3 What current models actually fail at, measured here

On AppWorld task `2a163ab_1` — *"Like all the venmo transactions from today
involving any of my roommates"* — with `phone` and `venmo` specialists available:

    [MAIN -> venmo] "List the usernames of my roommates on Venmo."
    [venmo -> MAIN] "ed_wilson, kri-powe, les_ball, tr_solo, ..."

Venmo has no address book. It substituted its **friends list** and answered
confidently. The true roommates — which `phone` returns without difficulty — are
Anthony Harrison, Anita Burch, Nicholas Weber. A different set entirely.

**The Main never queried `phone` at all.**

Two failure modes, both on the first runs, neither designed:
1. **The Main does not model what each specialist can possibly know.** It asks
   whoever performs the action, not whoever holds the fact.
2. **A specialist asked outside its competence guesses rather than declines.**

Upgrading the specialist to a frontier model does not fix (2) — it converts a
refusal into a *confident wrong answer* (§5.2), which is worse.

---

## 2. Construction method

### 2.1 The principle

**Mine an existing task library. Manufacture constraints. Inherit the judge.**

```
1. MINE       AppWorld: task, ground truth, environment, judge — all free
2. MEASURE    which tasks the reference solution proves are multi-app
                        → the roster comes from the task, never from us
3. CONSTRAIN  access / information / topology
                        → the multi-agent structure, and the ONLY thing we built
```

A constraint changes **who can do what**, never **what counts as done**. That is
the entire safety property.

The method is written up as a reusable skill:
[`skills/constraint-forged-multi-agent-tasks/`](../skills/constraint-forged-multi-agent-tasks/SKILL.md).

### 2.2 Task source and batch generation

**The roster comes from the task.** A task's specialists are the apps its
ground-truth solution actually touches (`forge/appworld/select.py`). We never
choose how many sub-agents a task gets, and never pad one with a role it does not
need.

That rule rejected two thirds of the corpus:

| filter | usable |
|---|---|
| naive — count every app the GT touches | **147 / 147 (100%)** |
| strict — drop `supervisor.complete_task` | **51 / 147 (34%)** |

`supervisor` is called in all 147 tasks and **every call is `complete_task`** —
the submit channel. It carries no information between apps. Counting it turns 96
single-app puzzles into "multi-agent" tasks with a decorative second specialist:
they would pass every check and measure nothing. 100% is the flattering number.

Largest real cluster: `phone`+`venmo` (30 tasks), then `file_system`+`spotify`,
`phone`+`simple_note`, `phone`+`simple_note`+`venmo`.

Batch generation is **reconfiguration, not invention**: 51 tasks × configs. Each
config is a different task for the model and the same task for the oracle.

### 2.3 Environment construction

We do not construct one. `pip install appworld`.

The only thing built is the **boundary**. AppWorld, the specialists and the oracle
live in a compose sidecar; the Main's container holds a 60-line HTTP client with
three verbs (`roster`, `ask`, `done`) and nothing else.

Verified on a rendered task — the agent's image contains exactly one file:

```
files in agent image: ['team']
violations: NONE
```

And from inside the running container:

```
import appworld            -> ModuleNotFoundError
curl /state (no token)     -> {"error": "forbidden"}
team ask spotify "..."     -> {"error": "you cannot reach 'spotify'"}
ls /tests                  -> does not exist during the agent phase
```

This is the direct lesson of §6's exploits. If AppWorld were in the Main's
container it could call `apis.venmo.*` directly, read the ground truth, or run
`evaluate()` — and the constraint layer would be a suggestion. **"The Main has no
API access" must be a property of the filesystem, not a sentence in a prompt.**

Harbor 0.18 supports this natively: `trial.py:842` discovers
`environment/docker-compose.yaml`, `constants.py:26` puts the agent in `main`.
The verifier also runs in `main`, so it authenticates to the sidecar with a token
written to `tests/` — which Harbor uploads only at verification time
(`verifier/verifier.py:147`), so the agent phase can never read the score.

### 2.4 Verification

We do not design it. AppWorld's `evaluate()` is programmatic (no LLM, no rubric),
state-based, and **side-effect aware** — it also fails an agent that reached the
goal destructively.

Reward is `passes / (passes + failures)` — a count of **AppWorld's own
per-requirement unit tests**. There is no `q_opt` here, no planted optimum,
**nothing we can get wrong**.

What the six requirements are, for `2a163ab_1`:

```
assert no new venmo.Transaction was added          <- passes for free
assert answers match
assert model changes match venmo.Transaction, venmo.TransactionLike
assert set of all new transaction likes is identical to ...
assert all newly liked transaction_ids are in recent_transaction_ids
assert all newly liked transaction_ids are in relative_transaction_ids
```

So **0.167 = 1/6 = did nothing**, and **1.0 = did everything and submitted the
right answer type**. (An action task's answer is `None`; submitting prose fails
`assert answers match` and caps the task at 5/6 — see §5.3, a bug of ours that hid
in that gap for two days.)

### 2.5 Difficulty control

Difficulty is the constraint layer's knobs. Each targets one listed capability.

| knob | targets | status |
|---|---|---|
| **access partition** (OPEN control / STAR) | decomposition, role assignment, role-awareness | **ships** — measured, 1.000 → 0.333, confound refuted (§5.2) |
| **visibility** (DOCS / NAMES) | role-awareness; capability discovery as a communication act | **ships flagged** — no score effect at this tier (§5.1) |
| **topology** (STAR / CHAIN) | Sub↔Sub communication | **NOT shipped** — unimplemented, fake signal (§5.4) |
| **delegation budget** | planning over trial-and-error | **not shipped** — unmeasured |

A budget is a constraint **on the world**, never a term in the reward.

**The ablation twin is free.** `OPEN` is the same task, the same oracle, the knob
off — one agent holding every API. It is *not* a deliverable; it is the ruler.
Any configuration that cannot beat it never tested coordination. Its scoring
1.000 is what makes the partitioned 0.333 mean something rather than "this task
is impossible".

### 2.6 Scale path, and the real bottleneck

| stage | cost |
|---|---|
| environment | free — `pip install`; 250+ prebuilt images exist for the SWE-smith family |
| oracle | free — `evaluate()` |
| task + ground truth | free — 732 tasks |
| selection | seconds — regex over ground truth, automated |
| **specialist LLM calls** | **the bottleneck** |

Measured: one partitioned rollout took **4.2 hours** (15,127s / 66 specialist
turns ≈ 229s per turn), almost all of it sleeping in 429 backoff against a 30k
TPM ceiling. An account limit rather than an inherent cost — but it is what stands
between 3 sample tasks and 408.

A subtler bottleneck: **only tasks whose OPEN control succeeds can measure a
knob** (§5.1). That filter needs real rollouts; it cannot be derived by
inspection.

Available scale from what exists today: **51 tasks × 8 configurations = 408
variants**, plus 51 free controls — by reconfiguring real tasks, not inventing
them.

---

## 3. Deliverables

- **Pipeline:** `forge/appworld/` — `select`, `partition`, `runtime`, `harbor`,
  `cli` (`measure` / `render`), `container/`.
- **Skill:** `skills/constraint-forged-multi-agent-tasks/SKILL.md`.
- **Harbor tasks:** `python -m forge.appworld.cli render --n 2`.
- **Evidence:** `sweep/appworld_span.json` (all 147 measured),
  `appworld_knobs*.json` (knob effects), `appworld_confound.json`,
  `appworld_validity.json`.
- **Gates:** `scripts/appworld_knob_sweep.py` (does each knob move the score?),
  `scripts/appworld_validity_probe.py` (is the drop the Main's, or a harness bug?).

---

## 4. Measurements

Three tasks, Main = gpt-5.6-sol, specialists = gpt-4.1. **These numbers postdate
the answer-type fix (§5.3); anything quoted elsewhere from before it was capped
at 0.833.**

| config | success | partial | delegations |
|---|---|---|---|
| `open` (control — one agent, all APIs) | **True** | **1.000** | 0 |
| `star-docs` | False | **0.333** | 7 |
| `star-names` | False | **0.333** | 2 |
| `chain-names` (unshipped, §5.4) | False | 0.333 | 12 |

**Model gradient on the control:** gpt-4.1 **0.17** vs gpt-5.6-sol **1.000** — the
thing `theory-of-mind` never had.

**Why the drop is real, and whose it is** (§5.2): hand a specialist the brief the
Main *should* have written, with the cross-app fact filled in, and it scores
**0.833→1.000**. The harness works, the specialist is capable. The whole gap is
the Main failing to work out that `phone` holds the names `venmo` needs.

---

## 5. What is not established

### 5.1 The partition saturates, so the finer knobs are unmeasured

All partitioned configs land on 0.333. `visibility` shows no score difference —
only a behavioural one. By the stated rule (a knob that does not move the score is
decoration) it is a delete candidate; the honest reading is that it is
**unmeasurable at this difficulty**, because the partition already dominates.
Telling "no effect" from "no headroom" needs an easier task or a stronger Main. It
ships flagged, not validated.

### 5.2 The headline was confounded, and the confound was refuted

`star`'s failures were specialist *refusals* ("Venmo cannot access the social
feed") — and the specialists were gpt-4.1 while the control's work was
gpt-5.6-sol. So the drop moved two variables. Re-run with gpt-5.6-sol
specialists: **still 0.167** under the old cap (n=2). The confound does not
explain the drop; the partition does. The upgrade only changed the failure mode,
from a refusal to a confident wrong answer.

### 5.3 The 0.833 ceiling was ours

For two days every action task was silently capped at 5/6 because the harness
submitted a prose summary where the ground truth returns `None`, failing
`assert answers match`. Measured: same work, prose → 0.833 `success=False`;
`answer=None` → **1.000 `success=True`**. `success=True` was never reachable
through the pipeline, and an earlier draft claimed "the ceiling is not pinned
either" — false. Fixed; §4 is the re-measurement.

### 5.4 `chain` is unimplemented, and its score was a fake signal

`chain` scored with `deleg=12` — exactly `max_steps` — and `answer='(out of
steps)'` every time. The Main can reach only `roster[0]`; the
specialist→specialist handoff the topology exists for is defined in
`Constraints.allowed_targets` and **called by nothing**. Its score reports the
step cap, not the topology. **A knob that moves the score by breaking the task is
worse than decoration.** Unshipped, with a test pinning it.

### 5.5 Three tasks, one seed each

Enough to show the partition dominates; not enough to rank configurations or put
an interval on the drop.

### 5.6 The instrument nearly lied, repeatedly

- **Floor effect.** The first sweep used gpt-4.1 as the Main: control *and*
  partitioned runs all scored 0.17, an apparent "the knob does nothing". The
  control was already failing. A knob's effect is unmeasurable when the control is
  on the floor.
- **A silent harness bug producing the same number.** gpt-5.x rejects
  `temperature=0`. Every call 400'd, an `except` swallowed it, and rows reported
  the untouched world's score — identical to genuinely-failing runs. Only
  `turns=0` told them apart.
- **Zero variance read as a triumph.** A 12-row sweep came back `min=max` in every
  cell. It hid both §5.3 and §5.4.

Outcome-only logging cannot distinguish *"the agent tried and failed"* from *"the
agent never ran"*. Rows now carry `ran`, and caught errors print.

### 5.7 What this dimension does not cover

The constraints *pressure* theory of mind and communication — §1.3 shows the Main
failing at exactly the ToM step — but nothing here **isolates** them. A failure
could be decomposition, briefing, or mind-modelling. Attribution needs
per-capability probes this does not have.

---

## 6. The retired v1, and why it is in this document

The first forge generated three dimensions from scratch — procedural generators,
planted optima, reference oracles, a CLEAN/VALID gate battery. It is the reason
the current design refuses to design an oracle, so it belongs here rather than in
an appendix.

### 6.1 `theory-of-mind` measured nothing, and everything was green

- The instruction named each topic's entry witness and said to follow referrals.
- Following referrals costs exactly `q_opt`, the optimum.
- So **obeying the instruction was optimal play.**

gpt-5.6 and gpt-4.1 both scored `asks == q_opt` on **12 of 12** runs at every
difficulty. Reward 1.0 everywhere → zero variance → zero advantage → **zero
gradient**. Worthless for RL, and every gate passed while it was true.

### 6.2 Four exploits, each scoring 1.0, all executed

| exploit | what it did |
|---|---|
| ground truth in the image | `cat /opt/maf/scenario.json` → the answer |
| forged transcript | fabricate one fake query → 1.0 with zero real work |
| shipped oracle | `import maf_dim; run_policy(inst, maf_dim.ORACLE)` |
| **seed brute-force** | the generator shipped in the image and is seed-deterministic → regenerate the instance, read the private keys → **defeats `/tests` isolation on every dimension** |

Root cause: a principle v1's design stated as a *virtue* — "single source of
truth: the dimension module is copied into the task so the in-container verifier
grades with exactly the code the selfcheck validated." That is what handed the
agent the generator.

The efficiency metric was its own trap: `quality = q_opt / asks` means fewer
queries score higher, so **forging a minimal transcript was strictly optimal** —
the anti-cheat mechanism rewarded cheating.

### 6.3 What survived, and still ships

- **`parallel-scheduling`** — its oracle re-executes the submitted schedule
  (`_check_schedule` re-checks every dependency, skill match and overlap, and
  recomputes the makespan), so lying costs exactly as much as solving. It ships
  and is Harbor-verified at reward 1.0.
- **The reward shape** `gate × quality`, the **CLEAN/VALID gate battery**, and the
  **ablation twin** — all still in use, including in the AppWorld dimension.
- **Gate V4 (dictation)**, added by the audit: every dimension must name the
  cheater that represents mechanically obeying its own instruction. It rejects
  `theory-of-mind` and `failure-recovery` independently.

### 6.4 What is quarantined

`theory-of-mind` and `failure-recovery` do not ship. `forge/forge_cli.py` refuses
to render them. The four exploits are pinned at reward 0 in
`forge/tests/test_adversarial.py`. Their constructs and the sidecar architecture
that would fix them are in
[`superpowers/specs/2026-07-15-deferred-dimensions-architecture.md`](superpowers/specs/2026-07-15-deferred-dimensions-architecture.md).
