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

Task `2a163ab_1..2` — *"Like all the venmo transactions from today involving any
of my roommates"* and variant. Main = gpt-5.6-sol, specialists = gpt-4.1.
**These postdate the answer-type fix in §5.3; everything measured before it was
capped at 0.833.**

| config | success | partial | delegations |
|---|---|---|---|
| **`open`** — the control: one agent, every API, no partition | **True** | **1.000** | 0 |
| `star-docs` — Main has no APIs, specialists have docs | False | **0.333** | 7–12 |
| `star-names` — Main has no APIs and does not know what they do | False | **0.333** | 2 |
| `chain-names` — unshipped, see §6 | False | 0.333 | 12 |

**The control is not a deliverable.** It is the ruler: the same task, the same
oracle, the knob turned off. Every shipped task is a partitioned one. The control
exists only to answer the question that makes 0.333 mean anything — *is this task
hard, or is it impossible?*

Its **1.000** answers it: gpt-5.6-sol solves this task completely when it holds
the APIs itself. Take the APIs away and make it coordinate, and it gets a third of
the way.

**The task has gradient** — the thing `theory-of-mind` never had. On the same
control: gpt-4.1 **0.17**, gpt-5.6-sol **1.000**.

### What 0.167 and 0.833 actually are — and the bug hiding behind them

I reported these as scores for two days before printing the six requirements
individually rather than the aggregate `5 pass / 1 fail`:

```
PASS  assert no new venmo.Transaction was added        <- free when you do nothing
FAIL  assert answers match
FAIL  assert model changes match venmo.Transaction, venmo.TransactionLike
FAIL  assert set of all new transaction likes is identical to ...
FAIL  assert all newly liked transaction_ids are in recent_transaction_ids
FAIL  assert all newly liked transaction_ids are in relative_transaction_ids
```

**0.167 = 1/6 = do nothing.** One requirement passes for free.

**0.833 = 5/6 = do all the work, then fail `assert answers match`.** The ground
truth for this task ends `return None` — it is an *action* task, and its answer is
`None`. My harness always submitted a prose summary. Measured directly:

| same work, submitted as | result |
|---|---|
| prose (`"Liked 4 transactions"`) | success=**False**, **0.833** — still failing `assert answers match` |
| `None` (what the GT does) | success=**True**, **1.000** |

**0.833 was my harness's ceiling, not the task's.** Every action task in every
sweep was silently capped at 5/6, and `success=True` was never reachable through
my pipeline. An earlier draft of this write-up said *"0.83 is not 1.0: the ceiling
is not pinned either"* — that was false. I had welded it shut myself.

Fixed: the harness now submits `None` when the Main reports an action. The
instruction had told the Main to say `completed` for action tasks all along; the
harness ignored it.

The scale is therefore closer to binary than the numbers suggest: **0.167 = did
nothing, 0.833 = did everything (capped), 1.0 = did everything and submitted the
right answer type.**

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

### Resolving it: the drop is the Main's, and here is the proof

Two experiments. First, `star` with **gpt-5.6-sol specialists**, isolating (a)
from (b):

All figures in this subsection are **pre-fix** (capped at 0.833 — §5.3), which is
fine: the comparison is internally consistent, and it is what I had at the time.

| config | specialists | partial | n |
|---|---|---|---|
| `open` (control) | — (Main does the work) | **0.833** | 3 |
| `star-docs` | gpt-4.1 | **0.167** | 3 |
| `star-docs` | **gpt-5.6-sol** | **0.167** | 2 |

Upgrading the specialists to the control's own model **changes nothing**.

But that alone did not prove the task sound — 0.167 was *exactly* the do-nothing
score (the `oracle` agent, which acts not at all, scores `passes=1, failures=5` =
0.167). Every partitioned run landing precisely on do-nothing looks far more like
a broken harness than like a hard task.

That suspicion was half right, and it is worth being precise about which half.
The harness *was* broken — but in the ceiling (§5.3), not the floor. Once the
answer-type bug was fixed the partitioned score moved to **0.333**: the Main does
accomplish something, it just cannot finish. **So the "partitioning reduces the
Main to doing literally nothing" reading was an artefact of my own cap**, and an
earlier draft of this write-up asserted it. The drop is real and larger than I
first reported (1.000 → 0.333), but it is not a wall.

So: **hand the venmo specialist a perfect brief** — the one the Main should have
produced, with the roommate names already in it:

    brief:  "On my Venmo social feed, find every transaction from today involving
             Anthony Harrison, Anita Burch, or Nicholas Weber. Like every one."
    report: "Liked all 4 transactions from today involving Anthony Harrison,
             Anita Burch, or Nicholas Weber."
    oracle: partial = 0.833  (5 pass / 1 fail)

**The specialist scores exactly what the unpartitioned control scores.** The
harness works. The specialist is capable. Nothing is broken.

| condition | partial |
|---|---|
| one agent holding every API | **0.833** |
| specialist + a perfect brief | **0.833** |
| **Main orchestrating for itself** | **0.167** |

The entire gap belongs to the Main: it never works out that it must ask `phone`
for the names before `venmo` can act on them. **That is the capability under
test, and it is the only thing the drop measures.**

This also explains why swapping the specialist model changed nothing: the
specialist was never the bottleneck. Swapping the *Main* does move the score —
0.17 for gpt-4.1 versus 0.83 for gpt-5.6-sol on the control.

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

### And the capability is real, because a better model does it right

Running the same task in Harbor with `terminus-2` / gpt-5.6-sol as the Main — a
real agent in the container, reaching the world only through `team` — its second
step reads:

    "Analysis: The phone specialist request has been sent, but no reply is
     visible yet, so the command is still processing."

It delegated to **`phone` first** — the specialist that actually knows — where the
in-process gpt-4.1 Main went straight to venmo and was taken in by the invented
roommate list.

Same constraint, same oracle: the weaker model asks the wrong specialist, the
stronger one asks the right specialist. That difference is the capability, and
nothing I wrote judges it.

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

- **Design doc:** [`docs/DESIGN.md`](docs/DESIGN.md) — structured to the brief's
  five questions, with the v1 retrospective that forced the method.
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
