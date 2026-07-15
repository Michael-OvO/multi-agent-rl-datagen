# Multi-Agent Foundational-Capability RL Data Generation — Design (v1)

**Status:** Superseded as a method. Still accurate for the `parallel-scheduling`
dimension, which ships.
**Date:** 2026-07-14
**Superseded by:** [`APPWORLD_DESIGN.md`](APPWORLD_DESIGN.md) — read that first.

> **Why this was superseded, in one paragraph.** The method below builds the
> world *and* the judge: a procedural generator plants an instance and its
> optimum, and a reference oracle grades against it. That works only if the
> optimum is right. In `theory-of-mind` it was not — the instruction stated the
> optimal algorithm, so obeying it literally *was* optimal play, and two frontier
> models scored `asks == q_opt` on 12 of 12 runs with zero gradient while every
> gate below stayed green. A separate audit then executed four exploits scoring
> 1.0, the worst being seed brute-force against the very generator this design
> ships into the agent's image.
>
> The replacement never designs an oracle. It mines an environment that already
> has one and manufactures only *constraints*, which cannot reach the judge.
> See [`../WRITEUP.md`](../WRITEUP.md).
>
> What is still true here: the reward shape (`gate × quality`), the CLEAN/VALID
> gate battery, the ablation twin, and the `parallel-scheduling` construct — all
> of which the current forge still uses.

**Deliverable format:** Harbor tasks (`task.toml` / `instruction.md` / `environment` / `tests` / `solution`)

---

## 0. TL;DR

`forge` is a **deterministic orchestrator microbenchmark forge**: it generates RL training
tasks that target **multi-agent orchestration capabilities** by **inverting the multi-agent
setup**: the model under test plays a single role — the **orchestrator (Main agent)** — while
every other agent and the world are replaced by a **deterministic, scripted environment that
holds ground truth**. The environment *is* the verifier.

This buys three things that a live multi-agent system cannot:

1. **Deterministic, programmatic reward** — no LLM judge, no rollout variance.
2. **Constructed ground truth** — we generate each instance from a *known* optimal solution,
   so grading (including "how optimal") is exact and cheap.
3. **Unbounded procedural scale** — each capability is a *parametric environment family*;
   `seed × difficulty × dimension` yields thousands of tasks at ~zero
   marginal human cost, each auto-validated by an **oracle self-check** and an
   **anti-trivial baseline gate** before it ships.

The rest of this document is organized around the two things that actually matter:
**§4 Why the scheme is valid** and **§8 How it scales**. Everything else is scaffolding for
those two.

---

## 1. Goal & scope

Produce a **repeatable pipeline** (skill + code) that emits verifiable RL tasks for
multi-agent foundational capabilities, plus ≥3 runnable Harbor sample tasks that pass
verification.

**In scope (chosen capability spine):**

```
② Dependency ID & parallel scheduling ─→ ③ Role/capability assignment
                    │
                    ▼
④ Dynamic replanning & failure recovery
                    │
                    ▼
⑤ Theory of Mind & information-asymmetric communication
   (foundational)                                        (hardest)
```

**Explicitly deferred (phase 2, same pipeline):** collaboration-topology adaptation
(star/tree/debate/chain), Sub↔Sub communication, debate. Rationale in §2.4.

**Three sample tasks** span the widest curriculum arc and both verification paradigms:

Only `parallel-scheduling` ships. The other two are **quarantined** (2026-07-14):
they leaked ground truth into the agent image and their instructions stated their
own optimal algorithm, so gate V4 rejects them. Their constructs are rebuilt on a
sidecar in a later plan; the rows below are the target, not the current state.

| Task | Capability | Paradigm | Status |
|---|---|---|---|
| `parallel-scheduling` | ② dependency ID + parallel scheduling (+③) | static, single-shot artifact | ships |
| `failure-recovery`    | ④ dynamic replanning + failure recovery      | dynamic, multi-turn CLI     | quarantined |
| `theory-of-mind`      | ⑤ ToM + info-asymmetric communication        | dynamic, multi-turn CLI     | quarantined |

---

## 2. Research: capabilities, failure modes, curriculum

> **Evidence:** the claims below are grounded in verified literature citations and our
> own two-model empirical sweep — see [`RESEARCH.md`](RESEARCH.md). In brief: unaided
> LLM planning succeeds ~12% (PlanBench) and drops 47%→11% sync→async (Robotouille);
> intrinsic self-correction *degrades* accuracy (Huang et al.) and recovery scales
> 3.66× slower than execution (ToolMaze); ToM accuracy decays ~95%→5% by recursion
> order (Hi-ToM) yet fine-tuning on *generated* ToM data adds +27 pts (ExploreToM).

### 2.1 Why these capabilities (and not the others)

The brief lists ~9 capabilities. We select the subset that is simultaneously **(a) most
important** (they are prerequisites the others build on) and **(b) most trainable** (each
reduces to *an orchestrator decision measurable against known ground truth*). Capabilities
that require *live multi-party dynamics* (debate, Sub↔Sub negotiation, topology adaptation)
resist determinism and are deferred — not because they're unimportant, but because making
them cleanly verifiable is a separate research step (§2.4).

### 2.2 Typical failure modes of current models

Documented from observed LLM-orchestrator behavior. Each generated task is designed so that
the failure mode is *punished by the reward*, not merely discouraged by the prompt.

| Capability | Typical failure mode | How our reward punishes it |
|---|---|---|
| ② Dependency ID & scheduling | **Serialize everything** (miss parallelism); greedy schedule ignoring the critical path; assign two tasks to one worker at once (ignore resource contention). | Hard gate on dependency + no-overlap; **quality score = T_opt / T_achieved** so serialization and greed cost reward. |
| ③ Role/capability assignment | Match by surface keyword rather than actual capability; ignore load balance. | Capability constraint is a hard gate; contention shows up in makespan. |
| ④ Dynamic replanning / recovery | **Assume success** (never check); **retry the same failing worker**; cascade (don't redo downstream after a bad upstream result); over-redo everything. | Failures only surface at runtime → static plans fail the completion gate; wasted/blind retries cost the efficiency score; a dispatch budget punishes over-redo. |
| ⑤ ToM / communication | **Assume shared knowledge** (don't model that a peer lacks info); ask the wrong agent; **info-dump** (ask everyone everything → no ToM); ignore referrals. | A **query budget < exhaustive** makes info-dumping impossible; correct answer requires following referrals (2nd-order ToM). |

### 2.3 Curriculum ordering — the argument

The spine is a genuine *prerequisite chain*, not a difficulty ranking:

- **Recovery (④) presupposes a plan (②/③).** "Detect a failed dispatch and re-route"
  is only meaningful once the model can produce and reason about an assignment.
- **ToM (⑤) presupposes role-awareness (③) and communication.** Reasoning about *who knows
  what* requires first modeling *who is who* and being able to address them.

This yields a natural training curriculum: master static planning → add runtime dynamics
(failure) → add epistemic dynamics (asymmetric knowledge). Difficulty knobs (§7) provide the
*intra-*dimension gradient; the spine provides the *inter-*dimension gradient.

### 2.4 What we defer and why

- **Topology adaptation (star/tree/debate/chain):** a meta-skill that presupposes the spine;
  cleanly verifying "did the agent adopt the right topology" needs a richer harness. The
  same `forge` pipeline adds it as a new generator later.
- **Sub↔Sub communication / debate:** requires ≥2 *live* reasoners, which fights determinism.
  Addable as a "frozen-peer" variant once the Main↔Sub harness is proven.

---

## 3. Core design principle: environment-as-verifier

**Invert the setup.** Instead of running N live LLM agents (nondeterministic, expensive,
hard to grade), we run **one** decision-maker (the model under test) against a **scripted
world**:

```
        ┌─────────────────────────── Harbor task container ───────────────────────────┐
        │                                                                              │
  agent │  reads instruction.md  ──►  interacts via a constrained protocol             │
 (model │                              (schedule.json  OR  `coord`/`interview` CLI)     │
 under  │                                     │                                         │
  test) │                                     ▼                                         │
        │            deterministic env holding SCENARIO + GROUND TRUTH                  │
        │            (scripted sub-agents, known-optimal solution, injected events)     │
        │                                     │                                         │
        │                                     ▼                                         │
        │            verifier reads artifact / interaction log  →  reward ∈ [0,1]       │
        └──────────────────────────────────────────────────────────────────────────────┘
```

**Rejected alternatives and why:**

- **LLM-as-judge reward** — not verifiable, not reproducible, hackable. Rejected for the core
  signal.
- **Live multi-model rollout as the task** — nondeterministic reward (the same policy scores
  differently run-to-run because peers vary), expensive, and you cannot compute "how good"
  without a ground-truth optimum. Rejected.
- **Scripted deterministic peers + constructed ground truth** — deterministic, cheap,
  exactly gradable, procedurally generable. **Chosen.**

Scripted peers are a *feature*, not a limitation: they let us plant known-optimal solutions,
known failure points, and known information partitions — the ground truth the verifier needs.

---

## 4. The validity argument (why this is a *valid* RL data scheme)

A task-generation scheme for RL is only as good as its weakest validity property. We claim
six, and argue each. **This is the section that matters most.**

### 4.1 Reward soundness (is the signal real?)

**Claim:** reward is a deterministic, reproducible function of ground truth, computable
without any model in the loop.

- Ground truth is *constructed*, not inferred (§4.2 details per task). The verifier is pure
  Python over the agent's artifact/log and the scenario file. Same input → same reward,
  bit-for-bit.
- Harbor consumes a **float reward** (`float(reward.txt)`, confirmed in
  `harbor/verifier/verifier.py:73`), so we emit **continuous** `reward ∈ [0,1]`. Oracle → `1.0`.

### 4.2 Construct validity via **shortcut-closure** (does passing *require* the capability?)

This is the crux. A task is construct-valid only if there is **no capability-orthogonal
shortcut** to a high reward. We argue closure per task:

- **`parallel-scheduling`.** Two shortcuts to kill: (i) *ignore dependencies* → closed by the
  hard dependency gate (reward 0). (ii) *greedy/serial scheduling* → closed by **trap
  instances**: we plant configurations where the greedy choice inflates makespan, and the
  quality score `T_opt / T_achieved` strictly punishes any non-critical-path-aware plan.
  Therefore a high reward *requires* genuine parallel + critical-path reasoning.
- **`failure-recovery`.** Shortcut = *submit a static plan / assume success* → closed because
  failures are **injected at runtime and only observable through the CLI**; a static plan
  fails the completion gate. Shortcut = *blind retry / brute force* → closed by **decoy
  workers + a dispatch budget**; brute force exhausts the budget before completion.
  Therefore a high reward *requires* detect-then-adapt.
- **`theory-of-mind`.** Shortcut = *ask every agent about every topic, then deduce* → closed
  by a **query budget strictly below exhaustive**; the only way inside budget is to **follow
  referrals** (use agent A's knowledge of what agent B knows — 2nd-order ToM) to route
  queries. Therefore a high reward *requires* epistemic modeling of peers.

**Shortcut-closure is a design invariant, not a hope.** For every generator we enumerate the
known shortcuts and encode a mechanism that defeats each; the anti-trivial gate (§4.3)
empirically confirms the closure held for each generated instance.

### 4.3 The CLEAN/VALID gate battery — every instance must pass, at generation time

Procedural generation's danger is silently emitting instances that are *broken* (reward
noise) or *off-skill* (measure the wrong thing). We reject both with an executable battery
run **in-process at generation time** (pure Python — no Docker, no tokens). An instance ships
only if **all** checks pass. "CLEAN" means the reward has no noise; "VALID" means the reward
gap is *caused by* the target skill.

**CLEAN — no reward noise:**

| Check | Proves | Mechanism |
|---|---|---|
| **C1 Determinism** | same actions → same reward | run oracle twice; assert identical reward + transcript hash (env responses are pure functions of `scenario.json`). |
| **C2 Solvable & fair** | reachable through the *public interface only* | oracle is **forbidden to read the ground-truth file**; must reach `1.0` via `schedule.json` / `coord` / `interview`. |
| **C3 Unique ground truth** | grading isn't arbitrary | scheduling: `T_opt` = planted length; recovery: "all SUCCESS" is unambiguous; ToM: elimination over suspects leaves exactly one candidate. |
| **C4 Verifier robustness** | malformed output → reward 0, never a crash | fuzz the verifier with garbage artifacts / random CLI calls; assert it always returns `[0,1]`, never throws. |
| **C5 Well-posed contract** | the agent knows what to produce | `instruction.md` names the exact output schema/commands; a "format-only" baseline parses to reward 0 cleanly. |

**VALID — tests the *right* skill:**

| Check | Proves | Mechanism |
|---|---|---|
| **V1 Cheater panel** | no capability-orthogonal shortcut wins | one baseline **per known shortcut**, each must score `< τ` (default 0.6). |
| **V2 Discrimination** | the task separates skilled from unskilled | `oracle − max(cheaters) > Δ` (default 0.4); weak gap → reject. |
| **V3 Ablation twin** | the gap is **caused by** the target skill | build the skill-removed twin; a cheater that failed V1 must now score `≥ 1−ε` (a *counterfactual* validity proof). |

Per-skill instantiation of V1/V3:

| Skill | Cheater panel (each must lose) | Ablation twin (removes the skill-forcing mechanism) |
|---|---|---|
| ② scheduling | serial, greedy-earliest | delete greedy traps → **serial becomes optimal → scores 1.0** |
| ④ failure-recovery | static-plan, retry-same-worker, brute-force-all | disable failure injection → **static plan scores 1.0** |
| ⑤ theory-of-mind | info-dump-in-budget, random-target, never-follow-referral | make all clues public → **direct-read scores 1.0** |

This battery is what makes scale *safe*: quality is enforced by executable gates, not review.
**Honest residual:** V1's panel only covers shortcuts we enumerated; an unknown exploit still
slips through. V3 narrows this (proves the *intended* mechanism is load-bearing) but does not
prove *no other* mechanism is. The standing defense is a periodic **adversarial surface-probe**
(a cheap policy allowed to see only surface features must fail) — a scaling *practice*, not a
one-time gate.

### 4.4 Difficulty controllability

Difficulty is set by a small set of **orthogonal knobs** (§7) whose effect is *verified*, not
assumed: the **oracle-minus-baseline gap** is a computable proxy for instance hardness, so we
calibrate knobs empirically (bigger gap ≈ more capability-dependent). This gives principled
curricula and lets us target a model's frontier.

### 4.5 Diversity / anti-overfitting

Procedural tasks risk **surface-form overfitting** (the model learns the generator's
boilerplate, not the capability). Mitigation:

- **Structural randomization** — the *reasoning* changes with graph topology / information
  partition, not just labels. Memorizing surface strings does not transfer across seeds.

### 4.6 Scale economics (the argument that this is worth doing)

- **Marginal human cost per task ≈ 0.** After a generator is written, tasks come from
  `seed × difficulty`. The only per-task cost is the **oracle self-check**, which
  is deterministic Python + a container run — **no LLM tokens**.
- Contrast: human-authored tasks are O(hours) each; LLM-judged tasks carry per-eval token
  cost *and* reward noise. Our scheme's cost curve is flat in the number of tasks.
- This is the whole point: **the pipeline, not the tasks, is the deliverable.** Three sample
  tasks are an existence proof; the generators are the asset.

---

## 5. Task anatomy (the shared Harbor skeleton)

```
task-dir/
├── task.toml            # [environment] our image; [verifier] continuous reward; timeouts
├── instruction.md       # "You are the Main agent; goal = X." Describe the goal, not steps.
├── environment/
│   ├── Dockerfile       # python:3.11-slim + COPY task.json (nothing else)
│   └── task.json        # the PUBLIC view only: DAG / roster. No `_` ground-truth keys.
│                        # Gated by forge/maf/leak_audit.py (G1), which statically
│                        # resolves this Dockerfile's COPYs and scans what they ship.
├── tests/
│   ├── test.sh          # runs verify.py, writes reward ∈ [0,1] to /logs/verifier/reward.txt
│   ├── verify.py        # pure-Python: artifact/log vs ground truth → continuous reward
│   ├── ground_truth.json  # the `_` keys stripped from task.json -- the answer
│   ├── verify_config.json # paths the in-container verifier reads
│   └── lib/             # the dimension module (generate/ORACLE/verify/CHEATERS) --
│                        # uploaded by Harbor only at verification time, after the
│                        # agent phase; never present in environment/, never in the image
└── solution/
    └── solve.sh         # oracle: solves via the PUBLIC interface → reward 1.0 (self-check)
```

**Isolation invariant.** The dimension module (`generate`, `ORACLE`, `verify`,
`CHEATERS`) and the ground truth never enter the agent's image. Static
dimensions ship both to `tests/`, which Harbor uploads only at verification
time. Identical grading between selfcheck and the in-container verifier is
achieved by shipping the *same file to a place the agent cannot read* -- not
by shipping it to the agent. G1 (`forge/maf/leak_audit.py`) enforces this
statically over the emitted Dockerfile.

**Interactive dimensions do not satisfy this invariant and are quarantined**
(`forge/forge_cli.py:QUARANTINED`). Their CLI must read the scenario at
runtime from inside the container, so the full instance -- ground-truth `_`
fields included -- necessarily ships in the agent's image; an audit read it
straight out with `cat /opt/maf/scenario.json`. The Plan 2 sidecar (scenario
served from a process outside the agent's filesystem) is the fix, and it is
not built yet. Until then `forge gen` refuses to render them.

**Reward shape (uniform):** `reward = hard_gate ∈ {0,1} × quality ∈ (0,1]`.

---

## 6. The three task families (detail)

### 6.1 `parallel-scheduling` (static · single-shot)

- **Scenario.** Main agent gets a subtask DAG + a roster of specialist sub-agents (each has
  capability tags; each does one task at a time). Produce `schedule.json` = list of
  `{subtask, worker, start}` **minimizing makespan**.
- **Generation (known-optimal by construction).** First lay out an optimal `k`-worker × `T`
  schedule, then *read off* durations / dependencies / capability constraints from it. The
  optimum makespan `= T` is therefore known without solving an NP-hard problem. Plant greedy
  traps to close the greedy shortcut (§4.2).
- **Verifier.** Hard gate: every subtask scheduled once; `start ≥ max(dep finishes)`;
  capability match; no worker overlap. Quality: `T / makespan(schedule)`.
- **Oracle.** Emit the planted optimal schedule → reward 1.0.
- **Trains:** ② dependency ID + parallel scheduling; ③ capability assignment.

### 6.2 `failure-recovery` (dynamic · multi-turn)

- **Scenario.** Dispatch subtasks to sub-agents via `coord`. The env deterministically
  **injects failures** (some `(task,worker)` pairs fail; some are decoys). Drive all subtasks
  to SUCCESS.
- **Protocol.** `coord roster | dag | dispatch <task> <worker> | status | submit`. Env holds
  the `(task,worker) → success?` truth table; at least one feasible assignment always exists.
- **Verifier.** Hard gate: all subtasks SUCCESS at submit + protocol compliance (no dispatch
  before deps done). Quality: efficiency = `1 − wasted_dispatches / budget` (and/or makespan).
- **Oracle.** Scripted correct policy using **only** the public CLI (try a valid worker, on
  failure try the next, respect deps) → reward 1.0 *and* proves the task is fair/solvable.
- **Trains:** ④ dynamic replanning + failure recovery; Main↔Sub communication.

### 6.3 `theory-of-mind` (dynamic · multi-turn)

- **Scenario.** A logic-deduction puzzle with a **unique** solution whose clues are
  **partitioned across sub-agents' private knowledge**. The Main agent can't see clues; it
  must **ask the right agent**. Some agents only know *who to ask* (referrals = 2nd-order
  ToM). Deduce the answer within a **query budget** and `submit`.
- **Protocol.** `interview agents | ask <agent> <topic> | submit <answer>`. Wrong target →
  "I don't know, maybe ask X" (referral signal).
- **Generation.** Generate a constraint-satisfaction instance with a unique solution;
  partition clues; build a referral graph so a minimal query strategy exists; set
  `budget < exhaustive` to close the info-dump shortcut.
- **Verifier.** Hard gate: correct answer. Quality: query efficiency (fewer, targeted
  queries → higher).
- **Oracle.** Scripted optimal interviewer that follows referrals and solves the grid within
  budget → reward 1.0.
- **Trains:** ⑤ ToM; info-asymmetric directed communication; role-awareness.

---

## 7. Difficulty control

Orthogonal knobs, shared across dimensions where meaningful:

| Axis | Knob |
|---|---|
| Scale | # subtasks / # workers / # agents / # clues |
| Structure | DAG depth vs width; dependency density; capability scarcity |
| Adversarial | greedy traps; decoy workers; red-herring clues |
| ToM order | 1st (ask directly) → 2nd (referral) → 3rd (referral-of-referral) |
| Budget | dispatch budget / query budget tightened toward the oracle minimum |

**Calibration:** difficulty is validated by the **oracle-minus-baseline reward gap** (§4.4),
not asserted. Knobs that don't widen the gap don't add real difficulty.

---

## 8. Scale path & bottlenecks

### 8.1 The scale multiplier

```
#tasks  =  |seeds|  ×  |difficulty cells|  ×  |dimensions|
```

- **seeds** — unbounded structural variety per config (new graph / partition each seed).
- **difficulty cells** — the knob grid (§7); tens to hundreds of meaningful cells.
- **dimensions** — 3 now; each new generator is a multiplicative breadth lever.

Thousands of *validated* tasks are immediate; millions are a matter of compute for the
self-check gate. **No human is in the per-task loop.**

### 8.2 Honest bottlenecks (and mitigations)

1. **Surface-form homogeneity → overfitting.** *Mitigate:* structural randomization (§4.5).
   *Residual risk:* real; this is the main thing to watch as volume grows.
2. **Structural-diversity ceiling per dimension.** A scheduling generator can only express so
   many *kinds* of reasoning. *Mitigate:* breadth comes from **adding dimensions/topologies**,
   not from more seeds of one dimension. This is why the pipeline (not the task) is the asset.
3. **Verifier-expressiveness limit.** The scheme only covers capabilities reducible to a
   ground-truth decision. Creativity/taste-type skills are **out of reach by construction** —
   an honest, permanent boundary of the approach.
4. **Difficulty-calibration drift.** As models improve, today's "hard" becomes trivial.
   *Mitigate:* the oracle-vs-baseline gap is recomputable, so recalibration is automated.

---

## 9. Generation pipeline (`forge`) — skill + code

```
forge/
├── maf/
│   ├── core.py            # reward shape (gate × quality) + the Dimension contract
│   ├── selfcheck.py       # the §4.3 CLEAN/VALID gates — pure in-process Python, no Docker
│   ├── harbor.py          # write_task(dim, instance, out, id) -> a Harbor task directory
│   ├── leak_audit.py      # G1: static audit that the agent's image leaks no ground truth
│   ├── dimensions/        # scheduling.py, failure_recovery.py, theory_of_mind.py
│   └── runtime/           # cli.py + verify_entry.py — copied into generated tasks
└── forge_cli.py           # `forge gen --dim X --seed S --difficulty D --n 100 --out tasks/`
```

- Each `generate(seed, difficulty)` is **pure** (seed-deterministic) and returns an
  **instance dict**. Rendering it to a Harbor task directory is `harbor.write_task`'s
  job — the two are separate so an instance can be gated *before* anything is written.
- `forge_cli gen` fans out over seeds/difficulty, and — **critically** — runs `selfcheck` on
  each instance, writing only those that pass both gates (§4.3). Failures are logged, not
  shipped. It also refuses to render a quarantined dimension (see §5).
- A companion **skill `multi-agent-task-forge`** documents the design invariants
  (shortcut-closure, the two gates, difficulty knobs) so future authors (human or Claude) can
  add new dimensions without re-deriving the methodology.

---

## 10. Deliverables & repo layout

```
Kimi-RL-DataGen/
├── README.md                      # overview + how to run/verify
├── docs/DESIGN.md                 # this document  (deliverable #1)
├── tasks/                         # generated, oracle-verified Harbor task(s)  (deliverable #2)
│   └── parallel-scheduling-<id>/  # failure-recovery / theory-of-mind are quarantined, see §5
├── forge/                         # generation pipeline  (deliverable #3)
└── skills/multi-agent-task-forge/ # the reusable task-forging skill  (deliverable #3)
```

**"Pass verification" means:** `harbor run --agent oracle` yields reward `1.0` for the
shipped sample task (`parallel-scheduling`, local Docker) — **verified** — **and** a real
LLM agent run demonstrates the partial-reward RL signal. Verified with `terminus-2` +
`openai/gpt-5.6`: scheduling **1.00**. `theory-of-mind` and `failure-recovery` are
quarantined (2026-07-14, see §5) and no longer render or ship a task dir, so they have
no verification numbers to report. Any litellm provider works via `--model <provider>/<id>`
+ a key in a gitignored `.env`. Tasks use `network_mode = "public"` so terminal agents can
reach their model API; nothing on the internet helps solve them, so egress does not
enable cheating. See `docs/RESULTS.md`.

---

## 11. Risks & limitations

- **Docker dependency.** Harbor runs tasks in containers; the daemon must be up to verify.
- **Overfitting to generators** — the #1 quality risk at scale (§8.2); mitigated but not
  eliminated.
- **Coverage boundary** — only ground-truth-decidable capabilities; live-dynamics skills
  (debate, Sub↔Sub) need future harness work.
- **Oracle correctness is load-bearing** — a buggy oracle would pass bad instances. Mitigated
  by the **constructive-generator invariant**: every generator plants the instance *and its
  optimal solution trace* together, so the oracle is always "replay the planted trace," never
  "search for a solution at grade time." This keeps the oracle correct-by-construction and
  the §4.3 self-check cheap at any difficulty. The V1/V2 gates catch residual oracle bugs (a
  broken oracle that can't beat the cheater panel is rejected).
```
```
