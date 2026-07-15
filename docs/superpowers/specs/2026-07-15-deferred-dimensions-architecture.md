# Deferred Dimensions — Architecture and Construct Design

**Status:** Design only. Not implemented, not scheduled.
**Date:** 2026-07-15
**Related:** `2026-07-14-outcome-based-sidecar-redesign.md` (the spec this elaborates)

This records the architecture and construct design for the two quarantined
dimensions so the thinking is not lost. **Nothing here is built.** Current work
is on the semantic layer for `parallel-scheduling` instead.

Both dimensions are quarantined because they leak ground truth into the agent's
image and because their instructions state their own optimal algorithm (gate V4
rejects both). Neither can be fixed by relocating files — their CLI must read the
scenario at runtime, inside the agent's container. Only a sidecar fixes them.

## 1. Shared architecture: the compose sidecar

The one piece both dimensions need. Harbor 0.18 supports it natively — this is
wiring, not new infrastructure.

```
┌─ main (agent) ─────┐         ┌─ maf-env (sidecar) ──────────┐
│ /usr/local/bin/team│  HTTP   │ scenario.json   ground truth  │
│   ~30-line shim    │ ──ask─→ │ maf_dim.py      gen+oracle+   │
│   curl → maf-env   │ ←resp── │                 verify        │
│                    │         │ ledger.jsonl    authoritative │
│ NO dimension code  │         │ state.json      world state   │
│ NO scenario        │         └──────────────────────────────┘
└────────────────────┘                      ↑
         │                        verifier GETs /state with token
         └─ tests/verify.py ──────────────────┘
            (runs in main at verify time)
```

**Why this closes what Plan 1 could not.** The agent has no filesystem path to
the sidecar — only a network socket. It cannot read the scenario (not in its
image), cannot brute-force the seed (no generator in its image), cannot run the
oracle (not in its image), and cannot forge the ledger (the sidecar writes it,
not the agent). The verifier grades the sidecar's state, never the agent's files.

**Harbor facts this relies on** (verified against Harbor 0.18 at
`~/.cache/uv/archive-v0/LfUwZBcktWC2okwjTmn_6/harbor`):
- `trial.py:842` discovers `environment/docker-compose.yaml`.
- `constants.py:26` — `MAIN_SERVICE_NAME = "main"`; the agent runs in `main`.
- `verifier/verifier.py` has no service targeting, so **the verifier also runs in
  `main`** — it must reach the sidecar over the compose network, not by reading
  its disk.
- `verifier/verifier.py:147` uploads `tests/` inside `verify()`, after the agent
  phase. So `/tests` does not exist while the agent runs.

**The token, and why it is needed.** The verifier needs the sidecar's terminal
state. The agent must not read it — belief state is exactly what the agent is
supposed to work to discover; a free `GET /state` would skip the whole task.
Since both run in `main`, the endpoint is gated by a token:

- generated at render time by `harbor.py`
- written to `tests/verifier_token.txt` → uploaded only at verify time, so the
  agent never has it
- passed to the sidecar via the **sidecar service's** `environment:` block in
  `docker-compose.yaml` → never enters the agent image

`docker-compose.yaml` sits in `environment/` (build context) but is not `COPY`d,
so it does not reach the agent image. `leak_audit.image_files()` reads COPY
directives specifically so it does not false-positive on it.

**Engineering constraint: keep it small.** Plain HTTP via stdlib
`http.server`, ~60 lines. Not MCP — MCP buys typed tools we do not need and adds
a dependency. The agent-side shim is a curl wrapper. This resolves the open
question in the parent spec toward the simpler option.

**Endpoints:**
- `POST /act {"cmd": ..., "args": [...]}` → public response. Sidecar appends to
  `ledger.jsonl` and updates `state.json`. Enforces the budget server-side.
- `GET /state?token=...` → terminal world state + ledger. 403 without the token.

## 2. `belief-tracking` (replaces `theory-of-mind`)

### What was wrong

The current task hands the agent its own algorithm: `render_instruction` names
each topic's entry witness, `OUTPUT_CONTRACT` says to follow referrals, and
following referrals costs exactly `q_opt`. Obeying the instruction *is* optimal
play. Both gpt-5.6 and gpt-4.1 scored `asks == q_opt` on 12/12 runs at every
difficulty — no gradient, and the task measured instruction-following. `_ask`
returning `{"result": "REFERRAL", "ask": <next agent>}` is a linked-list pointer,
not theory of mind.

### The construct

Explicit world state; each role has an observation history; a fact changes at
event *T*; roles that did not attend an event at or after *T* hold a **stale
(false) belief**. Nobody is told who is stale — it must be inferred.

- **Public:** the roster of roles; the event timeline with contents, from which
  the agent can determine *which* event changed the fact.
- **Hidden (sidecar only):** attendance — who was at which event.
- **Actions:** `ask <role>` → that role's attended events **and its co-attendees
  at each**; `tell <role>` → sets that role's belief to current. Each costs 1.
- **Goal state:** every role holds the correct belief.
- **Reward:** `quality = |stale roles ending correct| / |stale roles|`, gated on
  budget compliance. A do-nothing policy scores 0; the oracle scores 1.0.

### Why the budget is a constraint, not a metric

Pure outcome ("did everyone end up correct") is trivially reachable by telling
everyone — which needs no belief modelling at all. So the sidecar **enforces**
`budget = g + k` where `k` = number of stale roles and `g` = number of
attendance groups. Broadcast does not fit. The agent must work out *which* roles
are stale.

This is the resolution of "outcome-based vs still measures the skill": the reward
reads only the terminal state, and the budget makes that state unreachable
without the skill. A server-enforced budget bounds the world; `q_opt/asks` was a
metric over the path. Only the latter is the defect.

### Why asking is not just enumeration

Roles are generated in **attendance groups** — members of a group attended
identical events. Because `ask` returns co-attendees, one ask identifies a whole
group. So `g` asks suffice, and `g < n`. The agent must decide *who to ask next*
based on what previous answers revealed — genuine sequential decision-making, and
the thing that makes the trajectory worth training on.

- **ORACLE:** ask any uncovered role, learn its group from the co-attendee list,
  repeat until all roles are covered, then tell exactly the stale ones. Costs
  `g + k`.
- **DICTATION_CHEATER** (required by V4): the instruction states the goal and the
  action surface, never a procedure. The best literal-obedience policy is "tell
  roles in the order listed until the budget runs out" — it hits stale roles only
  by luck and must score below `tau`.
- **Other cheaters:** `ask_everyone` (spends the budget on asks, cannot tell);
  `tell_all` (budget < n, partial credit); `random`.
- **`ablate()`:** set every role stale (`k = n`) and `budget = n`, so "tell
  everyone" wins. V3 then sees a cheater reach 1.0 on the twin, confirming the
  real instance's gap is caused by the belief-inference requirement.

### Anti-dictation, explicitly

The instruction states the goal and the action surface and **never a procedure**.
It must not say "find the event that changed the fact, then check attendance."
The V4 declaration is what forces that discipline: the author has to answer
"what does mechanically obeying my instruction produce?" — theory-of-mind could
not answer it, which is the diagnosis.

## 3. `failure-recovery` (needs the most design work)

### What was wrong

Two things. It leaks like theory-of-mind. And it is degenerate the same way,
discovered during Task 4's review: the roster is generated pre-sorted
(`sorted(rng.sample(workers, size))`), so an agent that simply walks the
presented roster order on failure reproduces the oracle's sorted tie-break
exactly. Its scores (0.92–1.0) collapse the intended skill signal.

### The construct, sketched

The intent worth keeping is the one the docs claimed and the code never had: a
sub-agent that returns **plausible but wrong** output **without erroring**. The
current dimension announces failures; a failure that announces itself only tests
retry logic, not detection.

- **Public:** the task DAG and the worker roster.
- **Hidden (sidecar only):** which workers silently corrupt their output, and on
  which subtasks.
- **Actions:** `dispatch <subtask> <worker>` → returns a *claimed* result;
  `check <subtask>` → an independent, costed verification of one result.
- **Goal state:** every subtask completed *correctly* in the sidecar's world
  state — not "claimed complete".
- **Reward:** fraction of subtasks whose terminal state is genuinely correct,
  gated on budget.
- **Skill:** the agent cannot check everything (budget), so it must decide *what
  to verify* — spot-check, notice an inconsistency, re-route away from the bad
  worker. That is the actual silent-failure skill.

### The unresolved bit

Detection must be possible without being mechanical. If a corrupted result is
detectable by `check` alone, optimal play is "check everything the budget
allows," which is arithmetic, not skill. The corruption needs a *signal* — a
downstream inconsistency, a result contradicting another worker's — so that a
good agent knows *where* to spend checks. **Designing that signal so it is
inferable but not stated is the open problem.** Until it is solved, this
dimension should not be built; a half-designed construct is how the current one
got here.

### Anti-degeneracy requirements

- Roster order must be randomised, not `sorted(...)` — the exact bug above.
- The instruction must not state a checking procedure.
- `DICTATION_CHEATER` must be declared and must lose.

## 4. Gates these must pass

Unchanged from the parent spec; the shipping dimension already satisfies them.

| Gate | Rule |
|---|---|
| G1 leak audit | Agent image contains only the thin client. No scenario, no generator, no oracle, no verifier, no `.pyc`. |
| G2 dictation (V4) | `DICTATION_CHEATER` declared and scoring below `tau`. |
| G3 ablation (V3) | Removing the skill requirement collapses the oracle's advantage. |
| G4 cheater panel (V1/V2) | Every cheater below `tau`; oracle beats the best by `delta`. |
| G5 gradient | ≥2 models × ≥2 seeds × 3 difficulties must produce variance. All-1.0 rejects. |

Plus adversarial regressions, each scoring 0: read the scenario from the image;
forge the ledger; run the shipped oracle; brute-force the seed; zero real
queries; tamper with a sidecar response mid-run.

## 5. Estimated risk

The sidecar is a larger attack surface than Plan 1 touched — a network boundary,
a token, an authoritative ledger. Plan 1 needed three fix rounds on the leak
audit alone, and its final review still found four Important defects, including
a replacement test that reproduced the exact sin it replaced. Expect the sidecar
to be heavier, and expect the gates to earn their keep.
