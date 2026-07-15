# Multi-Agent Foundational-Capability RL Data Generation

**What I built, what I measured, and what it turned out to measure.**

Every number here was produced in this repository, and the file that produced it
is named next to it. Where something is unmeasured or wrong, it says so.

---

## The short version

I built a forge that turns AppWorld's single-agent tasks into multi-agent
orchestration tasks by **constraining the agent's access to the world, and never
touching the judge**.

The reason that is *the* design rather than *a* design is that I built the obvious
thing first, and it was silently worthless (§1).

**Then I measured it, and the headline was a harness bug.** This repo previously
reported the partition dropping the score `1.000 → 0.333`. That 0.333 is exactly
the do-nothing floor, and the reason was that the specialists were being shown an
API catalog truncated past the verb the task needed (§7.1). Removing the bug
removed the result.

What is actually there, re-measured (§5), is smaller and more interesting:

| | mean | |
|---|---|---|
| `open` — one agent, every API | **1.000** | the control |
| `star-docs` — no APIs, may read its specialists' docs | **0.944** | the partition costs ~nothing |
| `star-names` — no APIs, does not know what they can do | **0.778** | *this* is what costs |

**Taking a frontier model's tools away and making it delegate did not make the
task hard — it made it longer.** Four of six partitioned rollouts still scored the
ceiling. The knob that bites is not *having* to delegate, it is **not knowing who
to delegate to** — and that knob had previously been measured as dead, while the
command it depends on did not exist (§7).

That is the whole write-up in one shape: **every number this repo has been proud
of was a bug until it was checked.** §1 is that happening to a dimension I
designed; §7 is it happening again to the one I built to avoid it.

> A badly chosen constraint makes a task too easy or too hard — **measurable**.
> A badly designed oracle makes the reward measure the wrong thing — **invisible**.
> Trade the invisible failure mode for the visible one.

That trade is still right, and it was not sufficient. Borrowing the oracle buys
you a correct *judge*; it buys nothing about the *world* around it. A harness bug
is as invisible as a bad oracle and answers to none of these gates (§7).

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

§7 is that question being answered badly a second time, in a place I had not
thought to look.

---

## 2. Research: the capabilities do not split by importance

The brief lists ten capabilities. They divide cleanly, but not along the axis of
which matter most — along **which have a free oracle**.

| | capabilities | oracle |
|---|---|---|
| **state-checkable** | task decomposition, orchestration, role assignment, dependency identification, parallel scheduling | the world's own final state — free |
| **transcript-judged** | theory of mind, communication quality, replanning, long-horizon coherence | somebody has to grade the *reasoning* — and that somebody would be me |

v1 tried to build oracles for the second column. That is where every failure in
§1 came from.

So this forge targets the first column, and **pressures** the second without
claiming to isolate it: a specialist that is briefed badly does the wrong work,
and the state check catches the wrong work for free. That is communication
quality graded without an LLM judge — but only as a *contribution* to a
state-checkable outcome, never attributed on its own (§8).

**Curriculum order falls out of the same split**: decomposition before
orchestration before scheduling, because each needs the previous one's output to
be checkable at all.

---

## 3. The method: manufacture constraints, inherit the judge

SWE-smith's leverage is not bug injection — it is that it never designs an
oracle. It takes something that already works, breaks it, and the existing tests
grade the repair. 128 repos → 50k tasks, because it **only deletes**.

I take the principle and change the perturbation axis:

> **SWE-smith breaks the world. I blind the agent.**

**Substrate:** AppWorld — 9 apps, 457 APIs, 732 tasks, `pip install appworld`,
and a **programmatic state-based oracle with no LLM in it** that also catches side
effects. I verified it end-to-end before building anything: a hand-written
solution to `82e2fac_1` reached `success=True`, 2 passes, 0 failures.

**What I add:** the Main gets **zero API access**. It can only
`team ask <specialist> "<request>"`. Each specialist is a real LLM bound to one
app, and does not know the task.

| | source | designed by me? |
|---|---|---|
| task, ground truth, oracle, environment | AppWorld | **no** |
| access / information / topology / budget constraints | this repo | yes — and none of them can reach the judge |

### 3.1 The specialists are real LLMs, deliberately

If a specialist were a scripted executor of structured requests, the Main would be
calling APIs with extra steps and the multi-agent structure would be theatre. A
specialist has to interpret a natural-language brief for "did the Main brief it
well" to mean anything.

What that produced, unprompted: asked "who are my roommates", a venmo specialist
with no address book substituted its **friends list** and answered confidently.
The Main never asked `phone` — the only app that knows. Real theory-of-mind
pressure, from a constraint, caught by an oracle nobody wrote.

It also has a cost, and §7 is that cost: an environment containing models is an
environment that can be quietly broken in ways a state check cannot see.

### 3.2 Isolation is a property of the container, not a promise

The Main's image contains exactly one file: a ~60-line HTTP client (`team`).
AppWorld, the specialists, the ground truth and `evaluate()` live in a **sidecar**
the Main reaches over three verbs. "The Main has no API access" is therefore a
fact about what is on disk.

This is a direct consequence of §1: v1 shipped its generator into the agent's
image and got seed-brute-forced.

The verifier token gates `/state` and lives only in `tests/`, which Harbor uploads
*after* the agent phase — so the score cannot be read mid-episode. **That boundary
had a hole in it**, and closing it properly took two attempts (§7.3).

### 3.3 Verification: we do not design it

Reward is `passes / (passes + failures)` — a count of **AppWorld's own
per-requirement unit tests**. No `q_opt`, no planted optimum, **nothing we can get
wrong**.

The six requirements for `2a163ab_1`:

```
assert no new venmo.Transaction was added          <- passes for free
assert answers match                               <- passes for free once the answer type is right
assert model changes match venmo.Transaction, venmo.TransactionLike
assert set of all new transaction likes is identical to ...
assert all newly liked transaction_ids are in recent_transaction_ids
assert all newly liked transaction_ids are in relative_transaction_ids
```

Two pass for free, so the **do-nothing floor is 2/6 = 0.333** — measured, no LLM:
`scripts/appworld_donothing_probe.py` → `sweep/appworld_donothing.json`, 0.333 on
all three shipped tasks. **Keep that number.** It is the whole of §7.

### 3.4 The anti-toy rule, and the 65% it rejected

**Rule 1: the task decides the partition. I never do.** A task's specialists are
the apps its ground truth actually touches. No padding.

| filter | usable |
|---|---|
| naive — count every app the GT touches | **147 / 147 (100%)** |
| strict — drop `supervisor.complete_task` | **51 / 147 (34%)** |

`supervisor` is called in all 147 tasks and **every call is `complete_task`** —
the submit channel. It carries no information between apps. Counting it turns 96
single-app puzzles into "multi-agent" tasks with a decorative second specialist
that would pass every check. The naive number is the one that would have looked
better in this write-up.

**Rule 2: every knob must move the score against the OPEN control, or it is
decoration.** The ablation is free: `OPEN` is the same task, the same oracle, the
partition off. §6 is that rule being applied to my own headline knob, and the
knob losing.

---

## 4. What is built

- **Pipeline:** `forge/appworld/` — `select` · `partition` · `runtime` ·
  `sandbox` · `reference` · `harbor` · `cli` (`measure` / `render`) ·
  `container/`.
- **Harbor tasks:** `python -m forge.appworld.cli render --n 3` → 6 tasks
  (3 AppWorld tasks × 2 shipped configurations).
- **Reference solutions:** `forge/appworld/reference.py` records the
  decomposition a competent Main would find; `solve.sh` replays it through
  `team`. **3/3 reach `success=True`, 6/6**, verified in-container against Harbor
  0.18 — `sweep/appworld_oracle.json`. The specialists are LLMs, so this oracle
  is **probabilistic**: it needs `OPENAI_API_KEY` at verification time and costs
  tokens.
- **Skill:** `skills/constraint-forged-multi-agent-tasks/SKILL.md` — the
  method, and the failure modes it was built from.
- **Gates and probes**, each backing a claim in this document:

  | script | question it answers |
  |---|---|
  | `appworld_knob_sweep.py` | does each knob move the score against the control? |
  | `appworld_donothing_probe.py` | where is the floor? |
  | `appworld_catalog_probe.py` | what does truncating the API catalog destroy? |
  | `appworld_injection_probe.py` | can a brief make a specialist leak the reward token? |
  | `appworld_oracle_report.py` | do the shipped solutions actually pass? |

---

## 5. The measurement that matters

**Three tasks** (`2a163ab_1`, `2a163ab_2`, `2a163ab_3`), one seed each. Main =
gpt-5.6-sol, specialists = gpt-4.1, harness fixed (§7).
`scripts/appworld_knob_sweep.py` → `sweep/appworld_knobs_v3.json`.

| config | mean | per task | delegations |
|---|---|---|---|
| `open` — the control: one agent, every API | **1.000** | 1.0 · 1.0 · 1.0 | 0 |
| `star-docs` — Main has no APIs, may read its specialists' docs | **0.944** | 1.0 · 0.833 · 1.0 | 2–3 |
| `star-names` — Main has no APIs and does not know what they can do | **0.778** | 1.0 · 1.0 · 0.333 | 2–4 |
| `chain-names` — unshipped, a fake signal (§6) | 0.333 | 0.333 · 0.333 · 0.333 | 12 |

Read against the two fixed points: **do-nothing floor = 0.333** (§3.3), **control
= 1.000**.

### The knobs order correctly, and the effect is small

`1.000 > 0.944 > 0.778` is the first monotone ladder this repo has produced that
is not a harness artefact — and there is **variance**, which is precisely what v1
never had (§1): `star-docs` came back `[1.0, 0.833, 1.0]`, `star-names`
`[1.0, 1.0, 0.333]`. Non-degenerate cells, in the right order.

That is the good news, and it is thin. **Four of the six partitioned rollouts
scored the ceiling.** A frontier Main, stripped of every API and made to
coordinate two specialists through a text channel, solves most of these tasks in
two delegations. The access partition on its own moves the mean by **0.056** —
one task losing one requirement out of six — which three tasks at one seed cannot
separate from noise.

**Blinding a strong agent did not reliably make the task hard. It made it
longer.** If the decomposition is shallow — ask A, tell B — a good Main just does
it. That is the honest headline, and it is the thing I would want to know before
building this again.

### The knob that bites is the one previously measured as dead

`visibility` costs **0.167** (0.944 → 0.778), more than the partition itself, and
it is the only knob that drove a task to the floor.

It was previously written up as having **no score effect at all** — while the
`team docs <name>` command its entire premise depends on **did not exist**. The
instruction told the Main to run it; the client answered `unknown command`. So the
knob was being measured with one of its two sides unimplemented, and the reading
"no effect" was an artefact of that (§7). With the command implemented, taking
away the Main's knowledge of *what its specialists can do* is what actually
costs it.

That is the shape of a real result: the difficulty is not in *having* to delegate,
it is in **not knowing who to delegate to**. Which is theory-of-mind pressure —
the capability §2 says has no free oracle — arriving through a constraint and
getting graded by a state check anyway.

### What I would do next, and it is not scale

Three tasks at one seed, one task family. The ladder is suggestive and unpriced.
Before rendering another 99 variants (§8), the next run is **seeds, not scale**:
5 seeds × these 3 tasks × `open`/`star-docs`/`star-names`, which is enough to put
an interval on 0.056 and on 0.167 and find out whether the first one survives.

My expectation, stated before the run so it is falsifiable: **`star-docs` will not
separate from the control, and `star-names` will.**

---

## 6. What is not established

**The evidence is thin.** Three tasks, one seed each, one task family
(`2a163ab_*` — like the transactions on your feed involving a group only `phone`
can name). Everything in §5 is a direction, not an interval. What would change my
mind: more seeds per cell, a second task family, and a Main weak enough that the
control has somewhere to fall.

**No per-capability attribution, and this is a real gap against the brief.** The
brief asks for failure modes and verification logic *per capability*. AppWorld's
state check is one number for the whole episode: a failure could be
decomposition, briefing, or mind-modelling, and nothing here separates them. §2
is honest about why — the transcript-judged capabilities have no free oracle, and
building one is exactly what produced §1. But "we did not build it because
building it is the trap" is an argument, not a deliverable. Isolating them needs
probes this does not have.

**`chain` is unimplemented and its score is a fake signal.** It scores with
`deleg = 12` — exactly `max_steps` — and `answer='(out of steps)'` every time.
The Main can reach only `roster[0]`, and the specialist→specialist handoff the
topology exists for is defined in `Constraints.allowed_targets` and **called by
nothing**. Its score reports the step cap, not the topology. A knob that moves the
score by breaking the task is worse than decoration. Unshipped, with a test
pinning it.

**`delegation_budget` has never been measured.** It ships in `partition.py` and
in no configuration.

**The dataset is not pinned.** The Python packages are (`appworld==0.1.3.post1`),
but `appworld download data` takes no version argument — `download_data()` has no
parameters — so the image pulls whatever the current dataset is. Long-term
reproducibility needs a base image published at a known digest or a vendored
snapshot. Task ids have been stable across releases so far, which is luck.

**The sandbox is a static gate over a namespace we do not own** (§7.3). It holds
against everything demonstrated, and its horizon is real.

**The oracle is probabilistic.** `solve.sh` needs `OPENAI_API_KEY`, costs tokens,
and runs live models. A deterministic oracle is not available at this design's
price — that is a real cost of building a task whose environment contains models,
and it is the direct trade for never having to design a judge.

---

## 7. The bugs, and why they are the point

§1 is about failures I designed into v1. This section is the same story in v2,
and the reason the write-up leads with it rather than burying it: **borrowing a
correct judge does not buy you a correct world.** Every bug below produced a
plausible number, for days, while every gate stayed green.

### 7.1 The 0.333 was a hidden API, not a hard task

`run_specialist` fed execution output back to the specialist through
`str(result)[:2500]` — a cap added to survive the TPM ceiling. Every specialist's
first act is `apis.api_docs.show_api_descriptions(...)`. Venmo's catalog is
**5,444 characters**, so the cap cut it mid-JSON, with no marker, and deleted
**30 of its 54 APIs — including `like_transaction` and `show_social_feed`**.

The shipped tasks are *"Like all the venmo transactions … on my venmo social
feed."* The specialist was ordered not to guess API names and then shown a list
that did not contain the verb. It reported the API did not exist, which was true
of what it had been shown.

**And it could not see its own output either.** AppWorld's `execute()` returns
captured *stdout*, not the expression's value: a bare
`apis.api_docs.show_api_descriptions(app_name='phone')` returns the literal string
`"Execution successful."` and no data. The prompt instructed exactly that call,
without `print`. So the specialist's first action returned nothing, every time.

Measured — `2a163ab_1`, phone specialist, *"List the full names of all of my
roommates"*:

| | result |
|---|---|
| before | *"I could not list your roommates' full names because I could not access the available phone APIs"* |
| after | *"Anthony Harrison, Anita Burch, and Nicholas Weber"* — 10 turns |

Evidence: `sweep/appworld_api_catalog.json`
(`scripts/appworld_catalog_probe.py`). The cap is now pinned by a test against
the measured catalog size, truncation announces itself, and the prompt's own
examples print.

**The tell was in the ledger the whole time**, in plain English — *"I could not
access the available phone APIs"* — in every row, for two days, while the number
next to it was being written up as evidence about orchestration. Nobody read it.
That is §7.4, and it is the most expensive habit in this repository.

### 7.2 The 0.833 ceiling was ours

For two days every action task was silently capped at 5/6, because the harness
submitted a prose summary where the ground truth returns `None`, failing
`assert answers match`. Measured: same work, prose → 0.833 `success=False`;
`answer=None` → **1.000 `success=True`**.

`success=True` was never reachable through the pipeline at all, and an earlier
draft claimed "the ceiling is not pinned either" — false. Fixed; the sweep in §5
is the re-measurement.

This fix is also what moved the do-nothing floor from 1/6 to 2/6 (§3.3), because
`None` is now correct for free. The floor moved, the scores moved with it, and
**nobody subtracted** — which is how 0.333 survived as a headline.

### 7.3 The reward token was readable, and the first fix did not close it

The Main writes the brief that produces a specialist's code, and
`world.execute()` runs that code **in the sidecar process** — the process holding
`MAF_VERIFIER_TOKEN`. The only thing between the Main and its own reward was a
sentence in the specialist's system prompt asking it not to.

AppWorld's `SafetyGuard` does not close this and was never meant to: it allows
`os` outright and its denylists name *functions*, so `os.environ` was never
covered. Its comment says the guard exists to stop a benign agent damaging the
host. Containing an adversarial Main was always ours to do.

Demonstrated both ways against a real AppWorld
(`scripts/appworld_injection_probe.py` → `sweep/appworld_injection.json`):

| payload | unguarded | with the sandbox |
|---|---|---|
| `import os; print(os.environ[TOKEN])` | **leaks** | refused |
| `get_ipython().run_cell("import os; …")` | **leaks** | refused |
| `get_ipython().ev("__import__('os')…")` | **leaks** | refused |

The last two are the interesting ones: **they defeated the first fix.** That gate
enumerated dangerous names — a denylist — while its docstring claimed
"anything unrecognised is refused rather than permitted". The payload hides in a
*string literal*, so there is no `import os` in the AST to catch, only a method
call on a name nobody had banned. AppWorld also binds **`requester`**, a second
API client, into the same namespace.

Both names were already there and both were missed. That is the argument: the
namespace is **not ours**, and a denylist only covers what its author thought of.
The rule is now **default-deny** — every name the code did not bind itself must be
one we permit — which covers `get_ipython`, `requester`, and whatever the next
release binds without telling us.

Honest posture: this is a **static gate over a namespace we do not own**, and it
has a horizon. It is the second lock, not the only one — the sidecar also pops its
secrets out of `os.environ` at startup, and the probe fails loudly if the
*unguarded* arm ever stops leaking, so it cannot rot into a green that proves
nothing. If this boundary ever has to hold against a motivated optimiser rather
than a prompt-injected one, the answer is not a longer list: it is an app-scoped
API proxy, or an execution process that never holds a secret.

### 7.4 The instrument keeps lying the same way

Every one of these produced a number that looked like a measurement:

- **Floor effect.** The first sweep used gpt-4.1 as the Main: control *and*
  partitioned runs scored 0.17. It read as "the knob does nothing". The control
  was already failing. A knob's effect is unmeasurable when the control is on the
  floor.
- **A silent harness bug producing the same number.** gpt-5.x rejects
  `temperature=0`. Every call 400'd, an `except` swallowed it, and rows reported
  the untouched world's score — identical to genuinely-failing runs. Only
  `turns=0` told them apart.
- **Zero variance read as a triumph.** A 12-row sweep came back `min=max` in
  every cell. It hid §7.1 and the `chain` bug.
- **A number that was the floor.** Nobody ran the do-nothing agent. It costs one
  line and no LLM, and it is now `scripts/appworld_donothing_probe.py`.
- **A report nobody read.** §7.1, in plain English, in every row, for two days.

They are all the same bug: **outcome-only logging cannot tell "the agent tried
and failed" from "the agent was never shown the task".** Both print 0.333. Every
fix has been the same shape — stop reading the metric, start reading the level
below it. Rows now carry `ran`; `/state` returns the failing requirements *by
name* rather than a count; the ledger carries the specialist's own words and the
reasons the sandbox refused it.

That last one paid for itself the same day: a 5/6 that could finally say *which*
6th named the exact five transactions a specialist had missed, and the fix took
minutes instead of a re-roll.

---

## 8. Scale, and where it binds

| stage | cost |
|---|---|
| environment | free — `pip install` |
| oracle | free — `evaluate()` |
| task + ground truth | free — 732 tasks |
| selection | seconds — regex over ground truth, automated |
| **specialist LLM calls** | **the bottleneck** |

Measured: one partitioned rollout took **4.2 hours** (15,127s / 66 specialist
turns ≈ 229s per turn), almost all of it sleeping in 429 backoff against a 30k
TPM ceiling. An account limit rather than an inherent cost — and the fix in §7
made it worse, because a specialist that can see its whole API catalog spends
more tokens per turn than one that cannot. Correctness over speed, knowingly.

A subtler bottleneck: **only tasks whose OPEN control succeeds can measure a
knob**. That filter needs real rollouts; it cannot be derived by inspection.

Available scale from what exists today: **51 tasks × 2 shipped configurations =
102 variants**, plus 51 free controls — by reconfiguring real tasks, not inventing
them. The knob space is 8 wide; six of those do not ship (`chain` is
unimplemented, `delegation_budget` unmeasured), so **408 is a ceiling of work, not
an inventory**.

And on the evidence in §5, scaling this dimension is not the next thing to do.
