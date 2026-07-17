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

1. **An oracle you did not design.** State-based, ideally side-effect-aware.
   Free, and already validated by somebody else -- that is the whole of its
   value. Strongly prefer a substrate that has one.

   This used to read "a programmatic oracle with **no LLM in it**,
   non-negotiable," and cited this repo's v1 as the evidence. **The evidence does
   not support it.** The `theory-of-mind` dimension that died had no LLM in it at
   all: its reward was one line of hand-written arithmetic,
   `quality = min(1, q_opt/asks)`, and it was worthless because the instruction
   stated its own optimal algorithm, so obeying it was optimal play -- 1.0 on 12
   of 12, zero variance. What that indicts is an **unmeasured** oracle, not a
   language model. An LLM judge is a designed oracle, and it is *not* unauditable
   -- sample its verdicts against human labels and you have precision and recall.
   The v1 division was never measured that way, which is exactly why it stayed
   green.

   The rule that survives contact with the evidence: **inherit where you can;
   where you must design -- LLM, AST, or arithmetic -- measure its error rate
   before you trust it.**
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
| **SWE-smith** — 50k tasks, 128 repos | the repo's own pytest | strong oracle, but the seams are code modules → the task turns into SWE, not orchestration |
| **SWE-Gym / R2E-Gym** — 2.4k / 8.1k tasks | repo tests | same as above |
| **τ-bench / τ²-bench** | terminal DB state | good oracle; seams are thin (one domain API) |
| **MultiAgentBench** — has star/chain/tree topologies | **milestone KPIs, LLM-judged** | **costly** — its oracle is one you would have to validate before trusting, and that study is the expense a free oracle spares you. Not forbidden; priced. |
| orchestration-trace corpora | — | **do not exist.** The survey says causal credit "is not identifiable from realized on-policy traces alone" and ships a JSON schema instead of data |

The last row is the important one. **There is no multi-agent trace + environment
+ oracle corpus.** Everyone must manufacture the multi-agent structure. This
skill's entire claim is about *which layer* you manufacture — constraints, not
judges.

#### Disqualifiers, in the order they will bite

- **The judge is an LLM or a rubric, and nobody has measured it** → you are
  designing the oracle again and calling the design a description. Not
  disqualifying by itself: measure it against human labels, publish precision and
  recall, and it becomes a tool like any other. Disqualifying if you will not.
  (Costed honestly, that validation study is usually more expensive than finding
  a substrate that ships a free oracle -- which is why the free one is still the
  first thing to look for.)
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
| strict — drop the submit channel | **51 / 147 (34.7%)** |

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

#### The boundary you will forget is the specialist's

That checklist covers the *Main*. It says nothing about the specialist, and the
specialist is the one executing model-written code.

We shipped a sidecar with the Main's topology enforced in code and the
specialist's app restriction enforced in **its system prompt** — while the Main
wrote the brief that produced the specialist's code. So the Main could ask a
specialist to print the process environment, which held the verifier token, and
report it back. Then it could just read the score.

The environment sandbox will not save you: AppWorld's allows `os` and denies only
*functions*, so `os.environ` was never covered, and `execute()` runs in-process.
That is not a bug — that guard exists to stop a *benign* agent damaging the host,
and its source says so. **Containing an adversarial agent is always your job, not
your dependency's.** Read the guard before you rely on it.

Gate model-written code at the single choke point where it enters the world. Then
keep the secrets out of that process anyway, so the gate is not the only lock.

**Make the gate default-deny, and check that it is.** Our first one enumerated
dangerous names while its docstring claimed "anything unrecognised is refused" —
a denylist wearing an allowlist's description. It fell to two names that were
already in the namespace:

- `get_ipython().run_cell("import os; print(os.environ[TOKEN])")` — the payload
  is a **string literal**, so there is no `import os` in the AST to catch, only a
  method call on a name nobody banned.
- `requester` — the framework had quietly bound a *second* API client next to the
  one we were guarding.

The rule that holds: **every name the code did not bind itself must be one you
permit.** Variables, loop targets, arguments, imports are the code's own; every
free name resolves against a namespace *you do not own and did not write*. Only
default-deny covers what the next release of your dependency puts there.

And do not credit your gate for a dependency's check: `!shell` and `%magic` are
not parseable Python, so an AST gate never sees them — they were being stopped
by the framework's own parse step, in an ordering that is not yours to rely on.
Refuse what you cannot parse.

Ask the question that finds this class: not *"is the reward fake?"* but **"can the
reward be purchased?"** An agent that reads the scorer scores *better*, so every
validity gate you own will report success while it happens.

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

**The one that matters most: taking the tools away is not the hard part.**
Measured, after every bug below was fixed (n=3, one seed):

| | mean |
|---|---|
| one agent, every API (control) | 1.000 |
| no APIs, reads its specialists' real API catalogs | 0.944 |
| no APIs, **does not know what they can do** | 0.445 |

Blinding a strong agent did not make the task hard — **it made it longer**. Three
of six partitioned rollouts still hit the ceiling; the Main just asks A, tells B,
and is done. The `1.000 → 0.333` that made the partition look like it worked was
a harness bug, and removing it removed the result.

**The information constraint is still the one to design for** — access is the
packaging — but be warned by how this repo's own attempt to measure it went. The
`0.445` above is *not* the knob biting: two of those three rollouts scored below
the do-nothing floor because the Main honestly reported failure in prose and the
oracle wanted the action answer (`None`). **The reward paid 1/6 for lying.** And
the `docs` arm it is compared against had, until the last sweep, no docs at all —
the sweep ran an in-process path that never showed the Main a catalog, while the
shipped container served real ones. Two arms, one measured against the wrong
thing and the other measuring protocol compliance.

So: after three attempts this repo cannot tell you what its own headline knob
does. **Measure the knob's two arms against each other in the path that ships,
and check that a failed run cannot score worse than a silent one.** Both of those
are one afternoon and neither was done here until they were forced.

Before building the pipeline, name the *irreducible* difficulty and check that a
strong model actually fails at it. "The control succeeds and the partitioned run
does not" is the whole product.

**Zero variance is a smell, not a triumph.** A 12-row sweep came back
`open=0.833 (min=max)`, `every partitioned config=0.167 (min=max)`. It read as a
clean result. It hid two bugs. (`0.167 = 1/6` was the floor *before* the
answer-type fix; the same floor is `2/6 = 0.333` after it. Two numbers, one
floor, and the fix that moved it is why the next bullet says 0.333.)

**Compare every score against the do-nothing agent, and do it in code.** An agent
that performs no action at all scores whatever the free requirements are worth —
here 2/6 = 0.333 once the answer type was right. Every partitioned config also
scored 0.333. The result was written up as "the partition is hard" for two days.
It was the floor. The do-nothing baseline costs one line and no LLM; not having
it is why "hard task" and "broken harness" were indistinguishable.

**Never truncate a catalog the agent was told not to guess against.** We fed
execution output back through `str(result)[:2500]` to survive a TPM ceiling. The
first thing every specialist runs is `show_api_descriptions`; venmo's catalog is
5,444 chars; so the cap silently deleted 30 of 54 APIs — including
`like_transaction`, which *was the task*. The specialist reported the API did not
exist, which was true of what it had been shown. Truncation must announce itself,
and any cap must be pinned by a test against the measured worst case.

**Confirm the agent can see its own output.** AppWorld's `execute()` returns
captured *stdout*, not the expression value: a bare `apis.api_docs.show(...)`
returns the string `"Execution successful."` and no data. Our prompt instructed
exactly that call, without `print`. Every specialist's first act returned nothing
for two days. Run one turn by hand and *look at the bytes* before trusting a
sweep.

**Log the names, not the counts.** `passes=5, failures=1` cannot tell you which
requirement failed, and the oracle you need it for is the one that fails. The
underlying framework returned the names; we reduced them to `len()`. The first
0.833 we could actually diagnose named the exact five transactions the specialist
had missed, and the fix took minutes.

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
variables moved. The confound had to be tested (it lost — re-running with the
specialists upgraded still scored 0.167; `sweep/appworld_confound.json`) — but it
was nearly shipped.

**Measure the arm you ship, not the one that is convenient to run.** The fastest
harness is in-process; the thing you deliver is a container. Ours diverged twice
and both times the in-process version was the flattering one. (a) `star-docs`
told its Main *"their capabilities are listed above"* with nothing above it but
two role names, while the container served real catalogs over `team docs` — so
the documentation knob was measured with its documentation side unimplemented,
for every sweep this repo ever published. (b) The sweep converted three prose
phrasings to the action answer before submitting; the container converted none.
Those prefixes fired on **every control row and nothing else** — the control
being the only arm never told the answer protocol — and lifted it from 0.833 to
1.000. **A heuristic that rescues only your reference point is not a formatting
convenience.** Write a test that renders both paths and diffs them.

**Check that failing cannot score worse than not trying.** An agent that did the
work and reported it honestly scored **0.167**; an agent that did nothing and
said `completed` scored **0.333**. AppWorld's `assert answers match` wants an
action task's answer (`None`), so prose fails it — and the do-nothing baseline,
which submits `None`, clears a bar the honest failure does not. **The reward paid
1/6 for lying**, and no gate saw it, because every gate compares scores to the
floor and this was *under* the floor. The floor is not a floor: it is the score
of an agent that answers correctly and does nothing.

**If the partitioned score exactly equals the do-nothing score, suspect your
harness before you conclude the task is hard.**

## Non-negotiables

- Never design a reward. If you are computing an optimum, stop.
- Never let the agent's image contain the generator, the oracle, or the answer.
- Never pad a task with a specialist it does not need.
- Never ship a knob you have not measured.
- Green tests prove nothing. **Break the guarded property and watch it go red.**
