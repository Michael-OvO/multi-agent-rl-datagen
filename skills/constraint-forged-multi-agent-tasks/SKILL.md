---
name: constraint-forged-multi-agent-tasks
description: Use when building RL training tasks for multi-agent capabilities (theory of mind, decomposition, role assignment, Main↔Sub communication, failure recovery). Mines an existing single-agent environment that already has a free programmatic oracle, then manufactures the multi-agent structure by constraining the agent's access — never by designing a world or a judge.
---

# Constraint-Forged Multi-Agent Tasks

## The rule

**Manufacture constraints. Inherit the judge. Never design an oracle.**

If you design both the world and the judge, a flaw in the world becomes a flaw in
the reward — and it will be invisible, because your own tests will agree with
your own mistake.

A constraint cannot do that. It changes **who can do what**, never **what counts
as done**.

> A badly chosen constraint makes a task too easy or too hard — **measurable**.
> A badly designed oracle makes the reward measure the wrong thing — **invisible**.
>
> Trade the invisible failure mode for the visible one.

## Why this skill exists

A forge built the obvious way — procedural generators, planted optima, reference
oracles, a validity-gate battery — produced a `theory-of-mind` dimension where:

- the instruction named each topic's entry witness and said to follow referrals
- following referrals costs exactly `q_opt`, the optimum
- so **obeying the instruction was optimal play**

Two frontier models scored `asks == q_opt` on **12 of 12** runs at every
difficulty. Reward 1.0 everywhere → zero variance → zero advantage → **zero
gradient**. Worthless for RL. Every gate was green the whole time.

Four exploits also scored 1.0, the worst being seed brute-force: the generator
shipped inside the agent's image and was seed-deterministic, so the agent could
regenerate the instance and read ground truth that supposedly lived in `/tests`.

None of those failures were in the policy. They were in the parts that were
**designed**, and they were **invisible**.

## When this applies

You want RL data for multi-agent capabilities and you have discovered — as
everyone does — that no corpus of multi-agent traces + environments + free
oracles exists. The
[orchestration-traces survey](https://arxiv.org/html/2605.02801v1) states plainly
that causal credit "is not identifiable from realized on-policy traces alone" and
ships a JSON schema instead of a dataset. Benchmarks with real topologies score
with LLM judges or milestone KPIs.

So you must manufacture the structure. **The only question is which layer.**

| you manufacture | oracle risk |
|---|---|
| the whole construct + its oracle | **high** — this is how `theory-of-mind` died |
| **access / information / topology constraints** | **none** — no knob can reach the judge |

## The procedure

### 1. Find a substrate with a free oracle

Requirements, in priority order:

1. **A programmatic oracle with no LLM in it.** State-based, ideally
   side-effect-aware. This is non-negotiable — it is the whole point.
2. **Real, executable, installable.** Not a description of a world.
3. **Naturally partitionable** — its action surface must have seams (apps,
   services, tools, repos) that make plausible role boundaries.
4. **Ground truth available** for at least a train split, so you can measure.

Verified example: **AppWorld** — 9 apps, 457 APIs, 732 tasks, `pip install
appworld`, `evaluate()` compares database state against the goal and also fails
an agent that reached it destructively.

**Verify the oracle by hand before building anything.** Solve one task manually,
call `evaluate()`, and see `success=True`. If you cannot make the oracle say yes,
you do not have an oracle.

### 2. Measure the roster — never choose it

**The task decides the partition. You never do.** A task's specialists are the
seams its ground truth actually touches. Never pad a task with a role it does not
need; drop tasks that cannot be coordinated.

Watch for infrastructure masquerading as a collaborator. In AppWorld,
`supervisor.complete_task` is the submit channel and appears in **all 147**
ground-truth tasks:

| filter | usable |
|---|---|
| naive — count every seam the GT touches | 147 / 147 (100%) |
| strict — drop the submit channel | **51 / 147 (34%)** |

The naive number is the flattering one. It would ship 96 single-seam puzzles with
a decorative second agent — passing every check, measuring nothing.

**Write this rule as code with a test, not as a note.** Sabotage the test to
confirm it goes red.

### 3. Constrain, do not construct

Knobs that cannot reach the judge:

| knob | targets |
|---|---|
| **access** — which seam each specialist holds; the Main holds none | decomposition, role assignment |
| **information** — whether the Main sees capability docs, or must ask | role-awareness, discovery as a communication act |
| **topology** — who may talk to whom | Main↔Sub, Sub↔Sub |
| **budget** — how many delegations | planning over trial-and-error |

A budget is a constraint **on the world**, never a term in the reward. The reward
stays the substrate's terminal state check under every configuration.

**Scale comes from reconfiguration, not invention:** N tasks × M configs. Each
config is a different task for the model and the same task for the oracle.

### 4. Enforce constraints in the harness, never in the prompt

The agent under test must have **no filesystem path** to the environment, the
specialists, the ground truth, or the scorer. Put them in a sidecar; give the
agent a thin client.

"The Main has no API access" must be a property of the container, not a sentence
in a system prompt. Verify from inside the running container:

```
import appworld            -> ModuleNotFoundError
curl /state (no token)     -> 403
ask <off-roster specialist> -> refused
ls /tests                  -> does not exist during the agent phase
```

### 5. Make the specialists real LLMs

If a specialist is a scripted executor of structured requests, the Main is just
calling APIs with extra steps and the multi-agent structure is theatre. Only a
specialist that must interpret a natural-language brief makes "did the Main brief
it well" mean anything — and then a vague brief produces wrong work that the
oracle catches for free. That is how communication quality gets graded without an
LLM judge.

What this produces, unprompted: asked "who are my roommates", a venmo specialist
with no address book substituted its **friends list** and answered confidently.
The Main never asked `phone` — the only app that knows. Real theory-of-mind
pressure, from a constraint, graded by an oracle nobody wrote.

## The gates

Every knob must earn its place. **A knob that does not move the score is
decoration. A knob that moves the score by breaking the task is worse.**

| gate | rule |
|---|---|
| **control** | Same task, same oracle, partition off. It is free — just turn the knob off. Any config that cannot beat it never tested coordination. |
| **the control must succeed** | A knob's effect is unmeasurable when the control is already on the floor. This filter needs real rollouts; it cannot be derived by inspection. |
| **gradient** | ≥2 models must separate. All-0 carries as little signal as all-1. |
| **no dictation** | The instruction states the goal and the action surface, never a procedure. `theory-of-mind` stated its own optimal algorithm and nobody noticed for months. |
| **leak audit** | Assert what is actually in the agent's image, by parsing the Dockerfile's COPY directives. |

## Failure modes this skill was built from

Every one produced a number that looked like a measurement and was not.

**Zero variance is a smell, not a triumph.** A 12-row sweep came back
`open=0.833 (min=max)`, `every partitioned config=0.167 (min=max)`. It read as a
clean result. It hid two bugs.

**Check `deleg == max_steps`.** A topology scored 0.167 "because it was harder".
It was scoring the step cap: the specialist→specialist handoff it existed for was
defined and called by nothing, so the task was unsolvable.

**Check that the rollout ran at all.** gpt-5.x rejects `temperature=0`. Every call
400'd, an `except` swallowed it, and rows reported the **untouched world's
score** — numerically identical to genuinely-failing runs. Only a mechanism-level
field (`turns=0`) told them apart. Outcome-only logging cannot distinguish *"the
agent tried and failed"* from *"the agent never ran"*.

**Check what you actually changed.** A drop of 0.83→0.17 was attributed to the
partition while the specialists had *also* been downgraded to a weaker model. Two
variables moved. The confound had to be tested (it lost) — but it was nearly
shipped.

**If the partitioned score exactly equals the do-nothing score, suspect your
harness before you conclude the task is hard.**

## Non-negotiables

- Never design a reward. If you are computing an optimum, stop.
- Never let the agent's image contain the generator, the oracle, or the answer.
- Never pad a task with a specialist it does not need.
- Never ship a knob you have not measured.
- Green tests prove nothing. **Break the guarded property and watch it go red.**
