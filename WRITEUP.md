# Multi-Agent Foundational-Capability RL Data Generation

**What I built, what I measured, and what it turned out to measure.**

Every number here was produced in this repository, and the file that produced it
is named next to it. Where something is unmeasured or wrong, it says so.

---

## The short version

**The deliverable is a method, not a dataset and not an AppWorld wrapper.** It
turns an agentic task database that was never meant for multi-agent work into
multi-agent RL tasks, by **constraining the agent's access to the world and never
touching the judge** — and it measures which of the tasks it produces are worth
training on.

The whole of it is four moves. Only one is construction:

```
1. ADMIT      does the database qualify? four requirements (§3)
                          -> task, ground truth, environment, judge: all free
2. MINE       which tasks does the reference solution prove are multi-seam?
                          -> the roster comes from the task, never from me (§3.4)
3. CONSTRAIN  access / information / topology / budget
                          -> the multi-agent structure, and the ONLY thing I built
4. ACCEPT     floor < score < control, per cell
                          -> which renders are usable RL data, measured (§4)
```

**AppWorld is the substrate I ran it on, not the point.** It is an argument to
the method: it clears admission, so the method applies. Nothing in the four moves
is AppWorld-shaped, and §3 names the requirements precisely enough that you can
check another database against them without asking me. What I cannot tell you is
whether a second substrate works, because **I ran exactly one** (§6).

The reason that is *the* design rather than *a* design is that I built the obvious
thing first, and it was silently worthless (§1).

**On "quality", which is the word to distrust.** The method does not promise good
tasks. It promises tasks whose quality is *decidable*, and then reports the
verdict against itself: **1 of the 6 cells I shipped is usable RL data** (§4).
That is the method working. Move 4 is the difference between a forge and a
generator, because a generator cannot tell four things apart — the task is
unsolvable, the constraint never bit, the harness is broken, or the coordination
was really learned. All four print a number. §1 is what happens when nobody is
watching that.

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
| `star-names` — no APIs, does not know what they can do | **0.445** | and this is not the knob either (§5) |

**Taking a frontier model's tools away and making it delegate did not make the
task hard — it made it longer.** Three of six partitioned rollouts still scored
the ceiling. Giving the Main its specialists' real API catalogs moved the score by
**nothing**, and moved the delegation count from 2–3 to 3–5. The `star-names`
drop is not difficulty either: two of its rollouts scored *below* the do-nothing
floor for **honestly reporting failure in prose**, where a false `completed`
would have scored higher (§5).

That is the whole write-up in one shape: **every number this repo has been proud
of was a bug until it was checked.** §1 is that happening to a dimension I
designed; §7 is it happening twice more to the one I built to avoid it — most
recently to the sentence that gives the knob its name.

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
every difficulty — `sweep/tom_degeneracy.json` (3 difficulties x 2 seeds x 2
models; every cell 1.0). Reward 1.0 everywhere. Zero variance → zero advantage → **zero
gradient**. The dimension was worth exactly nothing for RL, and every gate passed
while that was true.

**Four exploits scored 1.0**, executed rather than inferred — with one caveat
recorded below the table:

| exploit | what it did |
|---|---|
| ground truth in the image | `cat /opt/maf/scenario.json` → the answer |
| forged transcript | fabricate 1 fake query → reward 1.0 with zero real work |
| shipped oracle | `import maf_dim; run_policy(inst, maf_dim.ORACLE)` |
| **seed brute-force** | the generator shipped in the image and is seed-deterministic → regenerate the instance, read the private keys → **defeats `/tests` isolation on every dimension** |

Three of the four are pinned by regression tests in
`forge/tests/test_adversarial.py`. **The forged transcript is not.** It does not
apply to `parallel-scheduling` — that submission is a schedule the verifier
re-executes, so forging it means solving it — and the interactive dimensions it
*did* apply to are the two now quarantined. Its regression test was deferred to
the sidecar and never written. Named here rather than quietly dropped, because a
gap that only the source file admits to is the same species of thing as the rest
of this section.

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
| **transcript-judged** | theory of mind, communication quality, replanning, long-horizon coherence | somebody has to grade the *reasoning*. That somebody can be a teacher model — but its accuracy is then a thing I have to measure, and that study is the cost the first column does not charge |

v1 tried to build oracles for the second column. That is where every failure in
§1 came from.

So this forge targets the first column, and **pressures** the second without
claiming to isolate it: a specialist that is briefed badly does the wrong work,
and the state check catches the wrong work for free. That is communication
quality graded without an LLM judge — but only as a *contribution* to a
state-checkable outcome, never attributed on its own (§6).

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

The rest of SWE-smith generalises too, and I take that as well: its Fail-to-Pass
rule — a candidate perturbation counts iff the repo's existing tests go red — is
an acceptance test that costs no judge. A graded oracle turns the flip into a
sandwich, and that is §4's validity rule.

### What the method asks of a database, before AppWorld is mentioned

The method is not a wrapper around AppWorld, and the honest way to show that is to
state the admission test **without naming a substrate**, then let one qualify. Four
requirements, in priority order:

| requirement | why, and what breaks without it |
|---|---|
| **a verifier you did not write** | free, and already validated by somebody else — that is the whole of its value. Without it, §1 happens to you |
| **real, executable, installable** | not a description of a world. If you cannot `pip install` or `docker pull` it, you will end up building it, and then you designed it |
| **a reference solution per task** | derives the roster *and* proves solvability. Without it you guess which tasks qualify, so you pad |
| **seams** | an action surface that divides along role boundaries — apps, services, repos, teams. No seams, no partition, no matter how you prompt it |

**Admission is necessary and not sufficient.** A database can ship a perfect
oracle and still have every task collapse into a single seam, which is why move 2
is a measurement rather than an assumption. The seams are also where the choice of
substrate stops being free: SWE-smith has the best oracle on the list, and its
seams are code modules, so a partition there produces a SWE task with extra
agents rather than an orchestration task.

Which parts of what follows are the method, and which are this substrate's glue:

| | ports to any admitted database | AppWorld-specific |
|---|---|---|
| **the rule** | the roster is what the reference solution touches; infrastructure never counts as a collaborator | `apis\.(\w+)\.(\w+)\(`, and that `supervisor.complete_task` is the thing to exclude |
| **the constraints** | access · information · topology · budget, none able to reach the judge | that a "seam" is an app and a specialist is bound to one |
| **the acceptance rule** | `floor < score < control`; yield reported, not assumed | that the floor is 2/6 and the control is OPEN |
| **the boundary** | the agent under test must have no filesystem path to the judge | the sidecar, `team`, and what AppWorld's `SafetyGuard` fails to cover (§7.3) |

**Substrate:** AppWorld clears all four — 9 apps, 457 APIs, 732 tasks,
`pip install appworld`, and a **programmatic state-based oracle with no LLM in
it** that also catches side effects. I verified it end-to-end before building anything: a hand-written
solution to `82e2fac_1` reached `success=True`, 2 passes, 0 failures — an early
manual check, and **its log did not survive**. The durable version of the same
check is `sweep/appworld_oracle.json`: the shipped reference solutions reach
`success=True` with 6/6 requirements, in-container. If you are repeating this
method on another substrate, that is the artefact to produce — seeing the oracle
say yes with your own eyes is the step everything downstream rests on, so it
should leave a file behind.

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
the Main reaches over four verbs (`roster`, `docs`, `ask`, `done`). "The Main has no API access" is therefore a
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

### 3.4 The anti-toy rules, and the 73.5% they rejected

**Rule 1: the task decides the partition. I never do.** A task's specialists are
the apps its ground truth actually touches. No padding.

| filter | usable |
|---|---|
| naive — count every app the GT touches | **147 / 147 (100%)** |
| strict — drop `supervisor.complete_task` | **51 / 147 (34.7%)** |
| information seam — a fact must cross between apps | **39 / 147 (26.5%)** |

`supervisor` is called in all 147 tasks and **every call is `complete_task`** —
the submit channel. It carries no information between apps. Counting it turns 96
single-app puzzles into "multi-agent" tasks with a decorative second specialist
that would pass every check. The naive number is the one that would have looked
better in this write-up.

The stricter gate matters after the submit channel is gone: 12 of those 51 tasks
touch two real apps but never move a fact between them. They can train parallel
dispatch, not the information-bearing coordination this method claims. The
`seams` command measures that distinction and `render` refuses rows outside it.

**Rule 2: the two selection measurements must agree.** `measure` records each
task's roster; `seams` records its cross-app data flow. `render` joins them by
task id and refuses duplicates, missing rows, or roster drift rather than quietly
shrinking or inflating the pool.

**Rule 3: every knob must move the score against the OPEN control, or it is
decoration.** The ablation is free: `OPEN` is the same task, the same oracle, the
partition off. §6 is that rule being applied to my own headline knob, and the
knob losing.

---

## 4. What is built

- **Pipeline:** `forge/appworld/` — `select` · `seams` · `partition` · `runtime` ·
  `sandbox` · `reference` · `validity` · `harbor` · `cli` (`measure` / `seams` /
  `render` / `judge`) · `container/`.
- **The validity rule:** `forge/appworld/validity.py` — a rendered cell is usable
  RL data only if `floor < score < control`. At or below the floor it carries no
  more signal than doing nothing; at or above the control the knob never bit.
  `python -m forge.appworld.cli judge` runs it over a sweep. **It reports 1 of 6
  shipped cells usable** — and says so as an *observation*, not a yield: one seed
  per cell cannot separate "always bottoms out" from "got unlucky once".
- **Harbor tasks:** `python -m forge.appworld.cli render --n 3` → 6 tasks
  (3 AppWorld tasks × 2 shipped configurations).
- **Reference solutions:** `forge/appworld/reference.py` records the
  decomposition a competent Main would find; `solve.sh` replays it through
  `team`. All six render a `solve.sh`; the **three `star-docs` tasks** were run
  in-container against Harbor 0.18 and reach `success=True` with 6/6 requirements
  each — `sweep/appworld_oracle.json`. **The `star-names` arm's solutions are
  unverified.** The specialists are LLMs, so this oracle
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
`scripts/appworld_knob_sweep.py` → `sweep/appworld_knobs_v5.json`.

| config | mean | per task | delegations |
|---|---|---|---|
| `open` — the control: one agent, every API | **1.000** | 1.0 · 1.0 · 1.0 | 0 |
| `star-docs` — Main has no APIs, reads its specialists' real API catalogs | **0.944** | 1.0 · 1.0 · 0.833 | 3–5 |
| `star-names` — Main has no APIs and does not know what they can do | **0.445** | 1.0 · 0.167 · 0.167 | 2 |
| `chain-names` — unshipped, a fake signal (§6) | 0.278 | 0.333 · 0.333 · 0.167 | 9–12 |

Read against the two fixed points: **do-nothing = 0.333** (§3.3), **control =
1.000**. And read the next two subsections before reading the ladder, because
neither knob means what the column suggests.

### The partition costs 0.056, and the docs knob costs nothing at all

The access partition moves the mean by **0.056** — one task losing one
requirement out of six — which three tasks at one seed cannot separate from
noise. **Three of six partitioned rollouts scored the ceiling.** A frontier Main,
stripped of every API and made to coordinate two specialists through a text
channel, solves most of these tasks anyway.

**Blinding a strong agent did not reliably make the task hard. It made it
longer.** If the decomposition is shallow — ask A, tell B — a good Main just does
it. That is the honest headline, and it is the thing I would want to know before
building this again.

`star-docs` is the sharper version of the same lesson. Until this sweep, its
Main was handed the sentence *"Their capabilities are listed above"* with nothing
above it but the two role names: the arm named for documentation had none, and
the shipped container — which really does serve catalogs over `team docs` — was
never what the sweep ran (§7.5). Now that the Main is given the real 2,838- and
5,444-character catalogs, the score is **unchanged at 0.944**. What changed is
that it delegates **3–5 times instead of 2–3** and takes **201s instead of 100s**.
Showing a Main what its specialists can do makes it more talkative, not more
correct.

### The `star-names` drop is the answer protocol, not the knob

`0.944 → 0.445` looks like the visibility knob finally biting. It is not.

Two of the three `star-names` rollouts scored **0.167 — *below* the do-nothing
floor of 0.333**. They got there by being honest: the Main failed to find the
transactions and said so — *"No Venmo transactions from yesterday involving your
siblings were found"* — and AppWorld's `assert answers match` expects an action
task's answer, which is `None`. Prose fails it. A Main that had falsely replied
`completed` would have scored 0.333.

**The reward pays 1/6 for lying.** That is not a knob and not a difficulty
gradient; it is an incentive built into the protocol's collision with the oracle,
and it argues for a curriculum that never rewards a false completion claim before
it argues for anything about visibility.

It was invisible until this sweep because the previous one had a heuristic that
converted `"No Venmo..."`, `"Unable..."` and `"Liked N..."` to `None` before
submitting — three prefixes read off this one task family. They fired on **every
open-control row and nothing else**, because the control was the only arm never
told the answer protocol; they lifted it from 0.833 to 1.000. The ceiling every
other number is read against was a string prefix (§7.5).

### What the validity rule says about all of it

`python -m forge.appworld.cli judge --sweep sweep/appworld_knobs_v5.json`:

| config | usable | |
|---|---|---|
| `star-docs` | **1/3** | two cells tie the control; one bites |
| `star-names` | **0/3** | one ties the control, two are below the floor |
| `chain-names` | 0/3 | all degenerate |

**1 of 6 shipped cells is usable RL data.** Note what this survived: between the
v3 sweep and this one the `star-names` mean moved by 0.333 and the verdict did
not move at all. A mean that swings by a third of the range while the answer to
*"can you train on this?"* stays identical is the argument for scoring cells
rather than averaging them.

One seed per cell, so this is an observation and not a yield (`validity.py`).

### Why `visibility` has now been mismeasured three different ways

It was previously written up as having **no score effect at all**. The cause was
the floor, not the knob: in both earlier sweeps *every* partitioned config sat on
it — `0.167 ×3` before the answer-type fix, `0.333 ×2` after — and a knob cannot
show an effect between two runs that are both bottomed out (§7.1). The catalog
truncation was pinning them there.

A separate bug had the same premise and never touched these numbers: the
`team docs <name>` command **did not exist** in the container, while the shipped
instruction told the Main to run it. That broke the *shipped task*; the sweep
runs `runtime.run_main` in-process and never invokes `team` at all. Two bugs, one
knob, and only one of them was ever in a number — which is exactly the confusion
that made me check.

Then this sweep found the third: the `docs` side was never implemented in the
path being measured, so the "0.167 cost" reported here until today was one prompt
sentence against another, one of which was false (§7.5). With the catalogs
actually present, the docs side costs **nothing**.

So `visibility` has been measured three times and has never once been measured:
first through a floor, then against an unimplemented arm, and now — with both
arms real — its apparent 0.5 turns out to be the answer protocol paying for
honesty. **I do not know what this knob does.** That is the current state of the
thing this write-up previously called its most interesting result, and it is a
better place to be than the previous two, because this time the instrument agrees
with the container.

### What I would do next, and it is not scale

Three tasks at one seed, one task family. The ladder is suggestive and unpriced.
Before rendering the other 72 variants (§8), the next run is **seeds, not scale**:
5 seeds × these 3 tasks × `open`/`star-docs`/`star-names`, which is enough to put
an interval on 0.056 and on 0.167 and find out whether the first one survives.

My expectation, stated before the run so it is falsifiable: **`star-docs` will not
separate from the control, and `star-names` will.**

---

## 6. What is not established

**The generality is argued, not demonstrated. This is the largest gap in the
document, and it is the one the framing invites.** I claim a method that applies
to any agentic task database clearing §3's admission test. I have run it on
**one**. Every substrate-independence claim above is therefore of the form *"no
step of this needs AppWorld"* — an argument from the construction, checkable by
reading it — and none is of the form *"it worked elsewhere"*. Those are different
kinds of sentence, and §1 is a monument to what happens when the first gets
reported as the second.

What is genuinely load-bearing and unproven: that a substrate can clear all four
requirements and *still* yield nothing, because admission does not measure seam
depth. AppWorld itself nearly demonstrates this — 96 of its 147 ground-truth
tasks are single-app puzzles (§3.4) — and I have no second database to say
whether 34.7% survival is typical, lucky, or bad. The cheapest falsification is
one afternoon: run move 2 against SWE-smith or τ-bench and publish the seam
distribution. **The skill cites a `funcy` module-deletion measurement suggesting
exactly this failure on a Python repo; that anecdote has no evidence file in this
repo and is marked as uncited there.** It is a recollection wearing a
measurement's clothes — §7.4's own category — and I am not going to let it do
work here.

**The evidence is thin.** Three tasks, one seed each, one task family
(`2a163ab_*` — like the transactions on your feed involving a group only `phone`
can name). Everything in §5 is a direction, not an interval. What would change my
mind: more seeds per cell, a second task family, and a Main weak enough that the
control has somewhere to fall.

**No per-capability attribution, and this is a real gap against the brief.** The
brief asks for failure modes and verification logic *per capability*. AppWorld's
state check is one number for the whole episode: a failure could be
decomposition, briefing, or mind-modelling, and nothing here separates them. §2
is honest about why — the transcript-judged capabilities have no free oracle. But
"we did not build it because building it is the trap" is an argument, not a
deliverable, and on inspection it is not even a good argument.

**§1 does not indict teacher models; it indicts unmeasured ones.** The
`theory-of-mind` dimension that died had no LLM anywhere in it. Its reward was
`quality = min(1, q_opt/asks)` — hand-written arithmetic — and it was worthless
because the instruction stated its own optimal algorithm, not because a model
graded it. What made that invisible was that nobody measured whether the reward
discriminated. A teacher model reading the ledger and attributing a failure to
decomposition, routing or briefing is a designed oracle too, and unlike a
division it can be checked: sample its verdicts against human labels and report
precision and recall.

So the honest position is that per-capability attribution is **affordable, and I
did not pay for it** — the validation study is the cost, and it is real. The
route I would take: keep the terminal state check as the only training reward,
use a teacher model for diagnosis and curriculum only, and measure its agreement
before letting it near a gradient. That ordering is what §1 actually argues for.

This applies to my own work with no discount: `seams.py` decides which 39 of 51
tasks coordinate, and it is a designed classifier whose error rate I have not
measured either. It is not safer for being an AST pass rather than a model — it
is unvalidated in exactly the way `q_opt/asks` was, and merely greppable.

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

| | result | evidence |
|---|---|---|
| before | *"I could not list your roommates' full names because I could not access the available phone APIs"* | recalled from a run whose log is not in this repo — **uncited** |
| after | *"Anthony Harrison, Anita Burch, and Nicholas Weber"* | `sweep/appworld_oracle.json` |

Evidence for the cap itself: `sweep/appworld_api_catalog.json`
(`scripts/appworld_catalog_probe.py`) — it records catalog sizes and the APIs the
old cap deleted, and holds no transcripts. The cap is now pinned by a test
against the measured catalog size, truncation announces itself, and the prompt's
own examples print.

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

- **Floor effect.** A knob's effect is unmeasurable when the control is already
  failing: both arms bottom out, and it reads as "the knob does nothing". I had
  written this up as a specific early sweep with a weaker Main. Checking it for
  this pass: **no committed file shows it** — every sweep in this repo's history
  ran `gpt-5.6-sol` as the Main, and none ever measured the control on the floor.
  So the anecdote was a recollection wearing a measurement's clothes, in the list
  of things that look like measurements and are not. The lesson is real and is
  now a branch instead of a memory: `validity.py`'s `CONTROL_FAILED` refuses to
  score any cell whose control is on the floor, rather than blaming the knob.
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
| selection | seconds — regex plus AST data-flow over ground truth, automated |
| **specialist LLM calls** | **the bottleneck** |

Measured: one partitioned rollout took **4.2 hours** (15,127s / 66 specialist
turns ≈ 229s per turn), almost all of it sleeping in 429 backoff against a 30k
TPM ceiling — `sweep/appworld_rate_limit_cost.json`, the pre-cap sweep, whose
next two rows are 6,795s and 6,704s. An account limit rather than an inherent
cost — and the fix in §7 made it worse, because a specialist that can see its
whole API catalog spends more tokens per turn than one that cannot. Correctness
over speed, knowingly.

A subtler bottleneck: **only tasks whose OPEN control succeeds can measure a
knob**. That filter needs real rollouts; it cannot be derived by inspection.

Available scale from what exists today: **39 tasks × 2 shipped configurations =
78 variants**, plus 39 free controls — by reconfiguring real tasks, not inventing
them. The knob space is 8 wide; six of those do not ship (`chain` is
unimplemented, `delegation_budget` unmeasured), so **312 is a ceiling of work, not
an inventory**.

And on the evidence in §5, scaling this dimension is not the next thing to do.
