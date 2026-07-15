# Multi-Agent Foundational-Capability RL Data Generation

**A write-up of what was built, what was measured, and what was wrong.**

Every number here was produced in this repository. Where something is unmeasured
or failed, it says so.

---

## The short version

I built a forge that turns AppWorld's single-agent tasks into multi-agent
orchestration tasks by **constraining the agent's access to the world, and never
touching the judge**.

The reason that is the design — rather than a design — is that I built the
obvious thing first, and it was silently worthless.

---

## 1. What went wrong first, and why it is the most useful result here

The first version of this forge generated three capability dimensions from
scratch: `parallel-scheduling`, `failure-recovery`, `theory-of-mind`. Each had a
procedural generator, a planted optimum, a reference oracle, and a battery of
validity gates. Everything was green.

Then I audited it.

**`theory-of-mind` was measuring nothing.** Its instruction named each topic's
entry witness and told the agent to follow referrals — and following referrals
costs exactly `q_opt`, the optimum. Obeying the instruction *was* optimal play.
Measured: gpt-5.6 and gpt-4.1 both scored `asks == q_opt` on **12 of 12** runs at
every difficulty. Reward 1.0 everywhere. Zero variance → zero advantage → **zero
gradient**. The dimension was worth exactly nothing for RL, and every gate passed
while that was true.

**Four exploits scored 1.0**, all executed for real, not inferred:

| exploit | what it did |
|---|---|
| ground truth in the image | `cat /opt/maf/scenario.json` → the answer |
| forged transcript | fabricate 1 fake query → reward 1.0 with zero real work |
| shipped oracle | `import maf_dim; run_policy(inst, maf_dim.ORACLE)` |
| **seed brute-force** | the generator shipped in the image and is seed-deterministic → regenerate the instance, read the private keys → **defeats `/tests` isolation on every dimension** |

The root cause was a principle the design doc stated as a *virtue*: "single source
of truth — the dimension module is copied into the task so the in-container
verifier grades with exactly the code the selfcheck validated." That is what
handed the agent the generator.

The efficiency metric was its own trap: `quality = q_opt / asks` means fewer
queries score higher, so **forging a minimal transcript was strictly optimal** —
the anti-cheat mechanism rewarded cheating.

### The lesson that shaped everything after

None of these failures were in the policy. They were in the parts **I designed** —
the oracle, the optimum, the isolation. And they were **invisible**: the tests
were green, the numbers looked good, and the whole thing measured
instruction-following while reporting theory of mind.

So the question stopped being *"what capabilities should I generate?"* and became
**"what can I build that I am incapable of getting wrong?"**

---

## 2. Research: the capabilities do not split by importance

The brief lists ten capabilities. They divide cleanly, but not along the axis the
list suggests:

| | capabilities | who judges "done"? |
|---|---|---|
| **Coordination over a world** | dependency identification, parallel scheduling, replanning, failure recovery, long-horizon planning | the world executes → **the oracle is free** |
| **Coordination over other minds** | theory of mind, topologies, Main↔Sub / Sub↔Sub communication, role-awareness | the minds must be simulated → **I design the oracle** |

`parallel-scheduling` survived my audit. `theory-of-mind` died. That is not luck —
it is this split. Scheduling's oracle re-executes the submitted artifact;
theory-of-mind's oracle was a number I computed and computed wrong.

**Curriculum order follows**: world-coordination before mind-coordination. Not
because it is conceptually prior, but because its oracle can be trusted. Building
a mind-coordination task before you can trust your own oracle is how you get
12/12 at 1.0 and never notice.

I checked whether the field has solved this. It has not: the
[orchestration-traces survey](https://arxiv.org/html/2605.02801v1) states that
causal credit "is not identifiable from realized on-policy traces alone" and
ships a JSON schema rather than a dataset. MultiAgentBench has topologies but
scores with milestone KPIs. **There is no multi-agent trace + environment +
free-oracle corpus.** Anyone doing this must manufacture the structure. The only
question is *which layer* you manufacture.

---

## 3. The method: manufacture constraints, inherit the judge

SWE-smith's leverage is not bug injection — it is that it never designs an
oracle. It takes something that already works, breaks it, and the existing tests
grade the repair. 128 repos → 50k tasks, because it **only deletes**.

I take the principle and change the perturbation axis:

> **SWE-smith breaks the world. I blind the agent.**

Same free-oracle trick, different knob. And the safety property is precise:

> A badly chosen constraint makes a task too easy or too hard — **measurable**.
> A badly designed oracle makes the reward measure the wrong thing — **invisible**.
> This trades an invisible failure mode for a visible one.

**Substrate:** AppWorld — 9 apps, 457 APIs, 732 tasks, `pip install appworld`,
and a **programmatic state-based oracle with no LLM in it** that also catches side
effects. I verified it end-to-end before building anything: a hand-written
solution to `82e2fac_1` reached `success=True`, 2 passes, 0 failures.

**What I add:** the Main gets **zero API access**. It can only
`team ask <specialist> "<request>"`. Each specialist is a real LLM bound to one
app, which does not know the task.

| | source | designed by me? |
|---|---|---|
| task, ground truth, oracle, environment | AppWorld | **no** |
| access / information / topology / budget constraints | this repo | yes — and none of them can reach the judge |

---

## 4. The anti-toy rule, and the 65% it rejected

The failure mode I was most worried about is a pile of sub-agents that look
impressive and measure nothing. Two rules guard against it.

**Rule 1: the task decides the partition. I never do.** A task's specialists are
the apps its ground truth actually touches. No padding.

It immediately rejected two thirds of the corpus:

| filter | usable |
|---|---|
| naive — count every app the GT touches | **147 / 147 (100%)** |
| strict — drop `supervisor.complete_task` | **51 / 147 (34%)** |

`supervisor` is called in all 147 tasks and **every call is `complete_task`** —
the submit channel. It carries no information between apps. Counting it turns 96
single-app puzzles into "multi-agent" tasks with a decorative second specialist
that would pass every check.

The naive number is the one that would have looked better in this write-up.

**Rule 2: every knob must move the score, or it is decoration.** The ablation is
free: `OPEN` is the same task, the same oracle, the partition off.

---

## 5. What the measurements say

Three tasks (`2a163ab_1..3`, *"Like all the venmo transactions from today
involving any of my roommates"* and variants), Main = gpt-5.6-sol, specialists =
gpt-4.1, 12 rows:

| config | n | partial (min–max) | delegations |
|---|---|---|---|
| `open` (control, no partition) | 3 | **0.833** (0.83–0.83) | 0 |
| `star-docs` | 3 | **0.167** (0.17–0.17) | 5.0 |
| `star-names` | 3 | **0.167** (0.17–0.17) | 4.3 |
| `chain-names` | 3 | **0.167** (0.17–0.17) | 12.0 |

**The task has gradient** — the thing `theory-of-mind` never had. On the same
control, gpt-4.1 scores **0.17** and gpt-5.6-sol scores **0.83**. And 0.83 is not
1.0: the ceiling is not pinned either.

**But zero variance is a smell, not a triumph**, and reading the rows rather than
the aggregate found two real bugs — one of them in the headline.

### Bug 1: `chain` was never implemented

`deleg=12.0` is exactly `max_steps=12`, in all three tasks, and every answer is
`(out of steps)`. In CHAIN the Main can reach only `roster[0]`; the
specialist→specialist handoff the topology exists for is defined in
`Constraints.allowed_targets` and **called by nothing**. The task is unsolvable
and the Main loops to the cap.

Its 0.167 does not mean "chain is harder". It means "chain is impossible". A knob
that moves the score by breaking the task is worse than decoration — it is a fake
difficulty signal. **It is unshipped**, with the reason recorded at the decision
point and a test pinning it.

### Bug 2: the headline comparison is confounded

The `star` answers are not orchestration failures. They are refusals *by the
specialists*:

    "Unable to complete: Venmo cannot access the social feed"
    "Unable to complete: phone contact search and Venmo social-feed unavailable"

The specialists are **gpt-4.1**. The OPEN control's work is done by
**gpt-5.6-sol**. So `0.83 → 0.17` changes two things at once:

- **(a)** the Main loses direct access — what I claim to measure
- **(b)** the API work is now done by a weaker model — a confound

The gate I was pleased to have passed does not cleanly separate *"partitioning is
hard"* from *"gpt-4.1 cannot drive venmo"*. The ground truth for these tasks uses
`venmo.show_social_feed`, so the API is there; the specialist failed to find it.

### Resolving it: the confound does not explain the drop

The clean experiment — `star` with **gpt-5.6-sol specialists**, isolating (a) from
(b):

| config | specialists | partial | n |
|---|---|---|---|
| `open` (control) | — (Main does the work) | **0.833** | 3 |
| `star-docs` | gpt-4.1 | **0.167** | 3 |
| `star-docs` | **gpt-5.6-sol** | **0.167** | 2 |

Upgrading the specialists to the control's own model **changes nothing**. The
0.66 drop is the partition, not the weaker model.

What the upgrade *did* change is the failure mode. With gpt-4.1 specialists the
Main gave up:

    "Unable to complete: Venmo cannot access the social feed"

With gpt-5.6-sol specialists it confidently concluded the opposite of the truth,
on both tasks:

    "No Venmo social-feed transactions from today involving my roommates"
    "No Venmo social-feed transactions from yesterday involving my roommates"

The control scores 0.83, so the transactions exist. **A stronger specialist did
not rescue the task — it converted a refusal into a confident wrong answer**,
which is the same failure the venmo hallucination showed at the very start, and
it is the one that matters: an orchestrator that is told "there is nothing there"
by a competent-sounding specialist has no way to know it was asked wrong.

(n=2 for the strong-specialist arm. Enough to refute the confound; not enough to
put an interval on the drop.)

I nearly shipped the confounded number. Zero variance across 12 rows should have
made me suspicious immediately — instead it read as a triumph.

### The failure mode the constraint exposes, unprompted

    [MAIN -> venmo] "List the usernames of my roommates on Venmo."
    [venmo -> MAIN] "ed_wilson, kri-powe, les_ball, tr_solo, ..."

Venmo has no address book. It substituted its **friends list** for "roommates"
and answered confidently. The real roommates — which the `phone` specialist
retrieves without difficulty — are Anthony Harrison, Anita Burch, Nicholas Weber.
A completely different set.

**The Main never queried `phone` at all.**

Two real failures, on the first runs:
1. The Main does not model *what each specialist can possibly know*. It asks
   whoever performs the action, not whoever holds the fact.
2. A specialist asked outside its competence guesses instead of declining.

That is theory of mind, produced by a constraint, graded by an oracle I did not
write. Compare the ToM dimension I built on purpose, which measured nothing.

---

## 6. What is not established

**The partition saturates, so the finer knobs are unmeasured.** All three
partitioned configs land on 0.17. What they do show is a clean monotone effect on
*effort*:

    open -> star-docs -> star-names -> chain-names
    0        3            6             12          delegations

Each constraint **doubles** the Main's delegations while the outcome stays flat.
The knobs are biting — but at this model tier the ladder is expressed as work,
not score. By my own rule they are delete candidates; the honest reading is that
they are **unmeasurable at this difficulty**, and telling "no effect" from "no
headroom" needs an easier task or a stronger Main. They ship flagged.

**One task, one seed** for the knob table. Enough to show the partition
dominates; not enough to rank configurations.

**The instrument nearly lied, twice** — both worth stating because both are the
same disease as the original:

1. **Floor effect.** The first sweep used gpt-4.1 as the Main. Control and
   partitioned runs all scored 0.17 — an apparent "the knob does nothing". The
   control was already failing.
2. **A silent harness bug producing the identical number.** gpt-5.x rejects
   `temperature=0`. Every call 400'd, my `except` swallowed it, and rows still
   reported `partial=0.17` — the untouched world's score, *the same number the
   genuinely-failing runs produced*. Only a mechanism-level field (`turns=0`)
   distinguished a harness bug from a real result.

Outcome-only logging cannot tell *"the agent tried and failed"* from *"the agent
never ran"*.

**Scope.** The constraints *pressure* theory of mind and communication — §5 shows
the Main failing at exactly the ToM step — but nothing here **isolates** them. A
failure could be decomposition, briefing, or mind-modelling. Attribution needs
per-capability probes this does not have.

---

## 7. Scale, and where it actually binds

| stage | cost |
|---|---|
| environment | free — `pip install`; 250+ prebuilt images exist |
| oracle | free — `evaluate()` |
| task + ground truth | free — 732 tasks |
| selection | seconds — regex over ground truth, automated |
| **specialist LLM calls** | **the bottleneck** |

Measured: one partitioned rollout took **4.2 hours** (15,127s / 66 specialist
turns ≈ 229s per turn), almost all of it sleeping in 429 backoff against a 30k
TPM ceiling. An account limit rather than an inherent cost — but it is what
stands between 3 sample tasks and 408.

A subtler bottleneck: **only tasks whose control succeeds can measure a knob.**
That filter needs real rollouts; it cannot be derived by inspection.

Available scale from what exists today: **51 tasks × 8 configurations = 408 task
variants**, plus 51 free controls. Not by inventing tasks — by reconfiguring real
ones.

---

## 8. Deliverables

- **Design doc:** [`docs/APPWORLD_DESIGN.md`](docs/APPWORLD_DESIGN.md) — structured
  to the brief's five questions.
- **Forging pipeline:** `forge/appworld/` — `select` (roster from the task),
  `partition` (constraints), `runtime` (Main + specialists), `harbor` (packaging),
  `cli` (`measure` / `render`).
- **Harbor tasks:** `python -m forge.appworld.cli render --n 3`
- **Evidence:** `sweep/appworld_span.json` (all 147 measured),
  `sweep/appworld_knobs.json` (knob effects).
- **Audit trail:** [`docs/superpowers/specs/`](docs/superpowers/specs/) — the
  exploits, the retired dimensions, and the architecture for what was deferred.

The isolation boundary is verified rather than asserted — on a rendered task the
agent's image contains exactly one file:

```
files in agent image: ['team']
violations: NONE
```

If AppWorld lived in the Main's container, the Main could call `apis.venmo.*`
directly, read the ground truth, or run `evaluate()`, and the constraint layer
would be a suggestion. That is not a hypothetical: it is precisely what the four
exploits did to the previous design.
