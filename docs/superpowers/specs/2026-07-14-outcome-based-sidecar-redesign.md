# Outcome-Based Sidecar Redesign

**Status:** Ready for review
**Date:** 2026-07-14
**Supersedes:** the isolation and reward sections of `docs/DESIGN.md`

## 1. Why

An audit of the shipped tasks found four working exploits and three construct
defects. Every exploit was executed against the real generated tasks, not
inferred from reading code.

| # | Defect | Dimensions | Evidence |
|---|--------|-----------|----------|
| 1 | Ground truth ships inside the agent image | tom, failure-recovery | `cat /opt/maf/scenario.json` yields `_culprit` |
| 2 | The graded artifact is agent-writable | tom, failure-recovery | forged transcript, 1 fake ask → reward 1.0 |
| 3 | The reference oracle ships with the task | tom, failure-recovery | `import maf_dim; run_policy(inst, maf_dim.ORACLE)` → 1.0 |
| 4 | Ground truth is regenerable from the shipped generator | **all three** | seed brute-force recovered `_planted` at seed=3 → 1.0 |
| 5 | The instruction states the optimal algorithm | tom | `asks == q_opt` in 12/12 sweep runs, two models |
| 6 | No gradient | tom | gpt-5.6 and gpt-4.1 both score 1.0 at every difficulty |
| 7 | Reward grades the path, not the outcome | tom, failure-recovery | `quality = q_opt / asks` |

### Root cause

Defects 1, 3, and 4 share one cause: `harbor.py:_copy_runtime` copies the entire
dimension module into `/app/lib/maf_dim.py`. That file holds `generate()`,
`ORACLE`, `verify()`, and `CHEATERS` — generator, reference solution, grader, and
cheater panel, all handed to the agent.

`DESIGN.md` presents this as an invariant: *"Single source of truth: the
dimension's Python module is copied into the task so the in-container verifier
grades with exactly the code the selfcheck battery validated."* The intent (DRY,
identical grading) is sound. The consequence is the vulnerability. Because
`generate()` is seed-deterministic, shipping it makes `/tests` isolation
decorative: the agent brute-forces the seed until the public fields match, then
reads the private ones out of its own regenerated instance.

This is why patching individual leaks failed. `parallel-scheduling` keeps its
ground truth in `/tests` and its verifier independently recomputes makespan — it
satisfies every principle we derived from first principles, and it is still
broken by defect 4.

### Why defect 7 is a defect

Grading the path contradicts the practice established by τ-bench, τ²-bench, and
AppWorld, which compare terminal environment state against an annotated goal
state rather than matching trajectories, because multiple distinct tool-calling
paths can satisfy the same goal. Grading path length both requires trusting an
agent-authored record and penalizes legitimate alternative strategies.

`Establishing Best Practices for Building Rigorous Agentic Benchmarks`
(arXiv:2507.02825) names two of our failures directly — grader-code isolation and
outcome validity — and reports that multiple major published benchmarks fail the
same checks. These are systemic errors, not idiosyncratic ones.

## 2. Goal and non-goals

**Goal.** Produce RL training data for multi-agent orchestration where the reward
measures the intended skill, across three dimensions at small instance counts.

**Non-goals.** Explicitly out of scope, and any claim to them must be removed
from the docs:

- Scale machinery: manifests, `generator_version` IDs, template variation,
  held-out configs, structural dedup. The target is a few instances per
  dimension; this work serves tens of thousands.
- Dimensions we do not implement: decomposition, higher-order ToM, liar/trust
  calibration, capability routing. `DESIGN.md` currently claims some of these.
- z3/CSP solving, random-valid baselines, `reward.json`. Claimed in `DESIGN.md`,
  absent from the code.

## 3. Architecture

### 3.1 The isolation boundary

Today one container holds everything. The agent runs as root inside it, so no
file permission can protect anything co-located with it.

```
BEFORE — one container, agent is root
┌─────────────────────────────────────────────┐
│ /opt/maf/scenario.json   ground truth       │  ← cat
│ /app/lib/maf_dim.py      generator+oracle+  │  ← import
│                          verifier+cheaters  │
│ /app/transcript.jsonl    the graded artifact│  ← forge
└─────────────────────────────────────────────┘

AFTER — two services, no filesystem path between them
┌─ agent container ─┐        ┌─ maf-env sidecar ──────────────┐
│                   │  HTTP  │ scenario.json    ground truth   │
│ thin client only: │ ──ask→ │ maf_dim.py       gen+oracle+    │
│ /usr/local/bin/   │ ←resp─ │                  verify+cheaters│
│   interview       │        │ ledger.jsonl     authoritative  │
│ (~30 lines,       │        │ world_state.json                │
│  no dim code)     │        └────────────────────────────────┘
└───────────────────┘                     ↑
                              verifier reads state+ledger from here
                              (harbor service_download_file)
```

The agent container receives a thin HTTP client and nothing else. It holds no
dimension code, so there is no generator to brute-force (kills 1, 3, 4). The
ledger is written by the service being asked, not by the asker, so there is
nothing to forge (kills 2). The verifier reads the sidecar's state, never the
agent's files.

### 3.2 Harbor wiring

Harbor 0.18 supports this natively; we are not building infrastructure.

- `environment/docker-compose.yaml` defines the two services. Harbor discovers it
  (`trial.py:842` checks `environment_dir / "docker-compose.yaml"`).
- `harbor/environments/compose_service_ops.py` provides `service_exec`,
  `service_download_file`, and `stop_service`. The verifier uses
  `service_download_file` to pull the sidecar's final state and ledger.
- Requires a compose-capable provider; Harbor raises a clear error otherwise
  (`trial.py:833`).

`parallel-scheduling` is single-turn: the environment never answers back, so
there is no interaction to log and no hidden state to serve. It needs no sidecar.
It still must stop shipping `maf_dim.py` (defect 4) — it ships `task.json` only,
and is graded out of container.

## 4. Reward model

**Primary reward is outcome-based.** Compare the sidecar's terminal world state
against the annotated goal state. Graded component-wise rather than binary, so a
partially-correct end state earns partial credit and the signal has gradient
without reintroducing path grading.

```
reward = gate * quality
gate    = 1 if the end state is valid (no constraint violated), else 0
quality = |achieved goal components| / |goal components|
```

**Effort is a constraint, not a metric.** This is the resolution of the tension
between "outcome-based" and "still measures the skill". A pure end-state check
is unforgeable but measures nothing if the goal is reachable without skill —
e.g. broadcasting an update to every agent trivially makes everyone's belief
correct. So the sidecar **enforces** a budget strictly smaller than the
brute-force cost. The budget does not appear in the reward; it makes the goal
state unreachable without modeling who actually needs the message.

This mirrors τ-bench's policy constraints: constraints bound the environment,
reward still compares terminal state. A server-enforced budget is a constraint on
the world. `q_opt/asks` was a metric over the path. They are not the same thing,
and only the latter is a defect.

**Effort is still recorded**, server-side, in the ledger — as a diagnostic for
calibration and analysis, never as a reward term. Because the sidecar writes it,
it is trustworthy for the first time.

## 5. Construct redesign

### 5.1 `belief-tracking` (replaces `theory-of-mind`)

The current task hands the agent the algorithm: the instruction names each
topic's entry witness and says to follow referrals, and following referrals costs
exactly `q_opt`. Optimal play is transcription, which is why both models hit
`asks == q_opt` on 12 of 12 runs and why the dimension has no gradient.

The redesign removes the pointer. Explicit world state; each role has an
observation history; a fact changes at time T, so roles that last observed before
T hold a **stale (false) belief**. Nobody is told who is stale — it must be
inferred from divergent observation histories.

- **Actions:** ask a role what it believes; tell a role the current fact.
- **Goal state:** every role holds the correct belief.
- **Constraint:** message budget < number of roles, so broadcast fails. The agent
  must identify *which* roles are stale.
- **Reward:** fraction of roles ending in the correct belief, gated on budget
  compliance.
- **Anti-dictation:** the instruction states the goal and the action surface, and
  never states a procedure.

### 5.2 `silent-failure-recovery` (replaces `failure-recovery`)

Retains the current construct's intent — a sub-agent returns plausible but wrong
output without erroring — and moves state and grading into the sidecar. Reward
becomes end-state-based: did the work actually get completed correctly, not how
many steps were used. Detailed design deferred to implementation; the isolation
and reward rules above are binding.

### 5.3 `parallel-scheduling`

Construct unchanged — it is a legitimate orchestration skill (allocate a task DAG
across a capability-typed team). Two changes only: stop shipping `maf_dim.py`,
and label it accurately as **single-turn planning**, not multi-turn interaction.
For RL it yields bandit-style data; the other two yield sequential-decision data.
Both are useful; they are different shapes and the docs must say which is which.

## 6. Validity gates

Measurement accuracy is enforced by gates that can reject a dimension, not by
assertion. Each gate falsifies one way of measuring the wrong thing. A dimension
that fails any gate does not ship.

| Gate | Falsifies | Rule | Status |
|------|-----------|------|--------|
| G1 leak audit | "we measure exploit-finding" | Render the task, then assert no file in the agent image contains the generator, oracle, verifier, seed, or ground truth. Assert brute-forcing the seed cannot reproduce the instance. | new — catches 1,3,4 |
| G2 dictation cheater | "we measure instruction-following" | A policy that mechanically executes the instruction's stated procedure must not beat threshold. | new — catches 5 |
| G3 ablation twin | **"we do not measure the skill at all"** | `ablate()` builds a twin with the skill requirement removed. The oracle's advantage over the cheater panel must collapse on the twin. If the score does not drop, the dimension was never testing the skill. | exists — promote to hard gate |
| G4 cheater panel | "we measure a dumb heuristic" | Every cheater scores below threshold. | exists |
| G5 gradient | "we measure nothing" | ≥2 models × ≥2 seeds × 3 difficulties must produce variance. All-1.0 or all-0.0 rejects the dimension. | new — catches 6 |

G1 and G2 are static and run in the test suite. G3 and G4 are in-process. G5
requires real model runs and gates release, not commit.

### Adversarial regression tests

The four executed exploits become permanent tests. Each must score 0:

1. Read the scenario from the agent image (file must not exist).
2. Fabricate a ledger (the verifier must not read agent-written files).
3. Import and run the shipped oracle (the module must not exist in the image).
4. Brute-force the seed against the shipped generator (the generator must not
   exist in the image).
5. Zero real queries: submit without interacting.
6. Tamper with a sidecar response mid-run.

## 7. Documentation corrections

Independent of the code, `docs/DESIGN.md` must be corrected. Every item below was
verified absent from `forge/`:

- Remove claims to: z3/CSP, random-valid baseline, liar dimension,
  silent-failure (as currently described), template variation, held-out configs,
  `reward.json`.
- Remove `**Status:** Draft for review` (line 3).
- Close the unclosed code fence (the file has 13 fences; the last is unterminated).
- Rewrite the "single source of truth" invariant — it is the root cause of
  defects 1, 3, and 4 and must not survive as a stated principle.
- Describe the project as a **deterministic orchestrator microbenchmark forge**.
  Do not claim decomposition or higher-order ToM.

## 8. Build order

Each step is independently verifiable, and the cheap falsifiers come first.

1. **Doc correction + retraction.** Pure removal; no code. Unblocks honest
   description immediately.
2. **G1 leak audit as a failing test.** Write it against the current tasks; it
   must fail, reproducing exploits 1/3/4. This is the regression harness for
   everything after.
3. **Sidecar for one dimension (`belief-tracking`), construct redesign included.**
   The heaviest step: compose file, thin client, sidecar service, ledger,
   out-of-container verifier. G1 must go green.
4. **G2 + G3 + G4 on `belief-tracking`.** Gates must pass on the redesign and
   must fail on the old construct — proving they have teeth.
5. **`parallel-scheduling`:** stop shipping the module; G1 green.
6. **`silent-failure-recovery`:** port to the pipeline proven in step 3.
7. **G5 gradient sweep.** Two models × seeds × difficulties; publish an auditable
   results JSON with mean, variance, and reward-hacking baselines.

Step 3 carries the risk. Step 2 makes that risk visible before it is spent, and
steps 1–2 deliver value even if 3 stalls.

## 9. Open questions

- Sidecar transport: MCP (`streamable-http`, which Harbor passes to the agent as
  a tool) versus a plain HTTP CLI shim. MCP is more standard and gives the agent
  typed tools; the CLI shim is closer to the current `interview` UX and simpler
  to grade. Decide in step 3.
- `silent-failure-recovery`'s goal state needs the same treatment §5.1 gives
  belief-tracking. Deferred to step 6.
