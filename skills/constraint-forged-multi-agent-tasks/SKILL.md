---
name: constraint-forged-multi-agent-tasks
description: Use when building RL training tasks for multi-agent capabilities (theory of mind, decomposition, role assignment, Main↔Sub communication, failure recovery). Mines an existing single-agent task library that already ships a free programmatic oracle — AppWorld, SWE-smith, tau-bench — measures which of its tasks can carry a partition, then manufactures the multi-agent structure by constraining the agent's access. Never designs a world, a task, or a judge.
---

# Constraint-Forged Multi-Agent Tasks

## The rule

**Mine an existing task library. Manufacture constraints. Inherit the judge.
Never design an oracle.**

The whole method in three moves:

```
1. MINE       an existing task library that already has a free programmatic
              oracle           -> task, ground truth, environment, judge: all free
2. MEASURE    which of its tasks the reference solution proves are multi-seam
                               -> the roster comes from the task, never from you
3. CONSTRAIN  access / information / topology
                               -> the multi-agent structure, and the ONLY thing
                                  you built
```

Step 1 is the enabler and the hard part. If you cannot find a library, **stop** —
do not fall back to writing a generator. That fallback is what this skill exists
to prevent.

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

### 1. Find the library — the step everything else rests on

**Do not build an environment. Do not write tasks. Find a library that already
has both, plus a judge.** Every later step is downstream of this one: if you
cannot find a substrate, the honest move is to stop, not to start writing a
generator.

The leverage is SWE-smith's, generalised. Its 128 repos → 50k tasks does not come
from clever bug injection; it comes from **never designing an oracle** — take
something that already works, perturb it, let the existing tests grade the
repair. Whatever you mine, you are looking for that same shape: *a working
artifact with a checker already attached.*

#### The four requirements, in priority order

1. **A programmatic oracle with no LLM in it.** State-based, ideally
   side-effect-aware. **Non-negotiable.** An LLM judge is another oracle you
   designed, with the added property that you cannot grep it for the bug.
2. **Real, executable, installable.** Not a description of a world. If you cannot
   `pip install` or `docker pull` it, you will end up building it.
3. **Ground truth for at least a train split**, so you can *measure* which tasks
   qualify instead of guessing.
4. **Seams.** The action surface must decompose along lines that make plausible
   role boundaries — apps, services, tools, repos, teams. No seams, no partition.

#### What is out there (surveyed 2026-07)

| library | oracle | verdict |
|---|---|---|
| **AppWorld** — 9 apps, 457 APIs, 732 tasks | state-based unit tests, **no LLM**, checks side effects | **use this** — seams are the apps |
| **SWE-smith** — 50k tasks, 128 repos, 250+ images | the repo's own pytest | strong oracle, but the seams are code modules → the task turns into SWE, not orchestration |
| **SWE-Gym / R2E-Gym** — 2.4k / 8.1k tasks | repo tests | same as above |
| **τ-bench / τ²-bench** | terminal DB state | good oracle; seams are thin (one domain API) |
| **MultiAgentBench** — has star/chain/tree topologies | **milestone KPIs, LLM-judged** | **disqualified** — no free oracle, which is the one thing you cannot supply yourself |
| orchestration-trace corpora | — | **do not exist.** The survey says causal credit "is not identifiable from realized on-policy traces alone" and ships a JSON schema instead of data |

The last row is the important one. **There is no multi-agent trace + environment
+ oracle corpus.** Everyone must manufacture the multi-agent structure. This
skill's entire claim is about *which layer* you manufacture — constraints, not
judges.

#### Disqualifiers, in the order they will bite

- **The judge is an LLM or a rubric** → you are designing the oracle again, only
  now it is unauditable. Walk away.
- **No ground truth** → you cannot measure which tasks qualify, so you will guess,
  so you will pad.
- **One seam** → nothing to partition. A single-API environment cannot carry
  roles no matter how you prompt it.
- **The oracle grades the trajectory, not the state** → multiple valid paths
  satisfy the same goal; path-matching will punish correct work. (This is why
  τ-bench, τ²-bench and AppWorld all converged on terminal-state checks.)

#### Verify the oracle by hand before building anything

Solve one task manually, call the judge, and see it say **yes**. Not "it looks
programmatic" — see `success=True` with your own eyes.

This took an hour on AppWorld and was worth it twice over: it proved the oracle
reachable *and* surfaced that the shipped ground-truth solutions are reference
implementations using internal helpers, which do not run in the agent sandbox. A
naive "run the GT to check the oracle" would have failed and looked like the
oracle was broken.

**If you cannot make the oracle say yes, you do not have an oracle.**

### 2. Measure which of its tasks can carry a partition

A task library is not a task set. Most of it will not qualify, and **which part
qualifies is measured, not judged**. The measurement is cheap — a regex over
ground truth, seconds for the whole corpus — and it is the same trick regardless
of substrate: *read what the reference solution actually touches.*

```python
# the roster is what the GT reaches for, not what we would like it to be
_CALL = re.compile(r"apis\.(\w+)\.(\w+)\(")

def derive_roster(solution_code: str) -> tuple[str, ...]:
    apps = {app for app, api in _CALL.findall(solution_code)
            if app not in _INFRA_APPS and (app, api) not in _INFRA_APIS}
    return tuple(sorted(apps))          # sorted: same task must render the same way
```

**The task decides the partition. You never do.** A task's specialists are the
seams its ground truth actually touches. Never pad a task with a role it does not
need; drop tasks that cannot be coordinated. `MIN_ROSTER = 2`.

#### Infrastructure will masquerade as a collaborator

This is where the mining goes wrong, and it goes wrong in the flattering
direction. In AppWorld, `supervisor.complete_task` is the **submit channel** and
appears in **all 147** ground-truth tasks:

| filter | usable |
|---|---|
| naive — count every seam the GT touches | 147 / 147 (**100%**) |
| strict — drop the submit channel | **51 / 147 (34%)** |

100% is the number that would have gone in the write-up. It would have shipped 96
single-seam puzzles with a decorative second agent — each passing every check and
measuring nothing.

Every substrate has one of these. Look for a seam that appears in *every* task
and carries no information *between* seams: submit channels, auth, logging,
documentation lookup. Exclude the **API**, not the seam — if a task genuinely
reads data from `supervisor`, that *is* a coordination edge and must count.

#### Then measure the structure, do not assume it

Even a qualifying library may have no partial order to exploit. On a Python repo,
deleting each module and recording which tests break gives the true dependency
matrix by **measurement** — and on `funcy` it returned only **4 distinct
breakage classes across 15 modules**, because its `__init__` imports everything.
The repo is nearly all-or-nothing and makes a weak orchestration task.

That negative result is the useful one: **the same measurement that builds the
task also filters the library.** Run it across the corpus, keep what has
structure. That is the scale story, and it is automated.

**Write these rules as code with tests, not as notes.** Sabotage each test and
confirm it goes red — the naive filter is *more* appealing than the strict one,
so the only thing keeping it out is a test that fails when someone relaxes it.

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
