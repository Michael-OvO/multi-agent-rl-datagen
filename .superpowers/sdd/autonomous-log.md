# Autonomous session — AppWorld orchestration dimension
Started 2026-07-15. User asleep; work autonomously, document, iterate.

## Approved direction (from conversation)
Substrate = AppWorld (732 tasks, 9 apps, 457 APIs, programmatic state oracle, zero LLM).
Method = do NOT build environment or oracle. Partition the existing environment's API
surface into app-specialist roles. Main gets no API access -> must decompose, assign,
communicate, recover. Oracle unchanged.

## Verified before this session (all by hand, in real containers)
- appworld installs; 732 tasks (train 90 / dev 57 / test_normal 168 / test_challenge 417)
- tasks genuinely span 2-3 apps (phone+venmo, file_system+spotify, spotify+supervisor)
- agent sandbox interface is `apis.<app>.<method>` -> namespace restriction is the partition
- ORACLE VERIFIED: hand-written solution on 82e2fac_1 -> success=True, 2 passes, 0 failures
- Real cross-app dependency exists: must call supervisor.show_account_passwords()
  before spotify.login() -> forces Main->Sub data passing

## Open design question to resolve FIRST
How autonomous is a sub-agent?
  (a) LLM sub-agent: real NL brief interpretation, real silent failure. Needs API key + costs.
  (b) Scripted executor of structured requests: deterministic/cheap, but then Main is
      just calling APIs with extra steps -> NOT multi-agent.
Deciding factor: information asymmetry must be REAL. If Main can see the app's API docs,
there is nothing to communicate. Main must discover capability THROUGH the specialist.

## Plan
1. Verify namespace partition works mechanically
2. Determine LLM sub-agent feasibility (API key in env?)
3. Spec
4. Build + gates
5. >=3 Harbor tasks, harbor run verified
6. DESIGN.md per assignment's 5 questions + write-up

## Log

## DESIGN LOCKED (user approved before sleeping, 2026-07-15)

Principle: **manufacture only constraints, always inherit the judge.**
ToM died because we built both the world and the judge, so a design flaw in the
world became a flaw in the reward (q_opt wrong -> 12/12 perfect, zero gradient).
A constraint layer cannot corrupt the judge: it changes WHO CAN DO WHAT, never
WHAT COUNTS AS DONE. A badly chosen constraint makes a task too easy or too hard
-- measurable. A badly designed oracle makes the reward measure the wrong thing
-- invisible. We trade an invisible risk for a measurable one.

What is mined (zero design): task, GT, oracle, environment -- all AppWorld's.
What is manufactured: only the access/information/topology/budget constraints.

### ANTI-TOY DISCIPLINE (user's explicit instruction)
1. **The task decides the partition, we never do.** Number of specialists ==
   number of apps the task's GT actually touches (measured by regex over GT).
   Never pad with extra agents for effect.
2. **Every knob must measurably change the score or it gets deleted.** If
   partitioning does not move the reward vs the all-APIs-to-Main control, the
   sub-agents are decoration -> cut. This is what V3 ablation is for.
3. Tasks solvable without coordination are FILTERED OUT, not padded.

### Partition taxonomy (each targets one listed capability; keep only what measures)
| knob | capability | keep if |
|---|---|---|
| access by app | decomposition, role assignment | mandatory (task-determined) |
| API-doc visibility | role-awareness, discovery via communication | moves score |
| topology star->chain | Sub<->Sub communication | moves score |
| budget | planning over flailing | moves score |
| unreliable sub | failure recovery, silent failure | moves score |

### Worked example (real task 2a163ab_1, verified)
"Like all the venmo transactions from today involving any of my roommates."
GT touches: phone (who are my roommates) + venmo (like transactions).
Partitioned: Main has zero APIs -> must ask phone specialist for roommate names,
then brief venmo specialist with those names. Vague brief -> wrong likes ->
AppWorld's evaluate() catches it (it checks both completion AND side effects).
Control/ablation is free: give Main all APIs; if score is unchanged, the
partition never tested coordination.

### Work order
1. measure all 732 tasks (regex GT -> app span) -> filter >=2 apps
2. build constraint layer
3. MEASURE each knob's effect; delete knobs that do not move the score
4. Harbor packaging
5. >=3 tasks, harbor run verified
6. DESIGN.md per assignment's 5 questions + write-up

---
## [1] MEASUREMENT DONE — and it rejected 65% of the tasks

Measured all 147 GT-bearing AppWorld tasks (train 90 + dev 57).

**The naive filter lies.** Counting every app the GT touches:
  2 app: 96 | 3 app: 42 | 4 app: 9  ->  147/147 (100%) "multi-agent"

**But `supervisor` is called 147x and EVERY call is `complete_task`** -- the
submit channel. Zero real data dependencies. It is infrastructure, not a
collaborator. Counting it inflates every single-app task into a fake pair.

**Strict filter** (drop supervisor.complete_task):
  1 app: 96  <- single-app, no coordination possible, DISCARD
  2 app: 42
  3 app:  9
  -> **51/147 (34%) genuinely usable for multi-agent**

Largest real cluster: phone+venmo (30 tasks). Then file_system+spotify,
phone+simple_note, phone+simple_note+venmo.

Artifacts: appworld_span.json (naive), appworld_span_strict.json (strict).

**This is the anti-toy discipline working.** Had I shipped the naive number I
would have delivered 147 "multi-agent" tasks of which 96 are single-app puzzles
with a decorative second agent -- and they would all have passed, and looked
great. Exactly the failure the user warned about.

### Caveat found while measuring (matters for the write-up)
The GT is a *reference implementation* using internal helpers
(`apis.spotify.access_token_from(main_user)`), not the agent-facing API path.
An agent must instead call `supervisor.show_account_passwords()` then
`spotify.login()` -- I did exactly this in the verified hand-solve. So regex over
GT measures the *coordination* span correctly but does NOT capture the agent's
credential-lookup step. That step is a trivial lookup, not coordination, so
excluding it is right -- but the write-up must state that GT-regex measures
inter-app coordination, not total agent work.

### Next
build the constraint layer; then MEASURE whether partitioning actually moves the
score vs the all-APIs-to-Main control. If it does not move, the sub-agents are
decoration and the design dies here.

---
## [2] PROTOTYPE RUNS — and an unplanned finding that validates the design

Built: app-specialist sub-agent (real LLM, sees ONLY its own app's docs + the
Main's NL brief, never the task) and Main (real LLM, ZERO API access, only
`DELEGATE <specialist> :: <request>`).

**Specialist works.** phone specialist, given only "Who are my roommates?",
read its API docs, found show_contact_relationships, logged in via
supervisor credentials, answered: "Anthony Harrison, Anita Burch, Nicholas Weber."
Real exploration -- it first guessed `list_contacts` (does not exist), failed,
read the docs, recovered.

**THE FINDING (unplanned, and it validates the whole design):**
On task 2a163ab_1 the Main asked the WRONG specialist:
    [MAIN -> venmo] "List the usernames of my roommates on Venmo."
    [venmo -> MAIN] "ed_wilson, kri-powe, les_ball, tr_solo, ..."
venmo has no address book. It substituted its *friends list* for "roommates" and
answered confidently. The true roommates (phone) are Anthony Harrison, Anita
Burch, Nicholas Weber -- a completely different set.

This is a REAL silent failure, and AppWorld's oracle catches it (wrong
transactions liked + side-effect check). We did not design this phenomenon; it
emerged from the access constraint alone. It is exactly the target capability:
the Main must model WHAT EACH SPECIALIST CAN POSSIBLY KNOW -- venmo cannot know
who your roommates are. That is theory of mind, produced for free by a
constraint, and graded by an oracle we did not write.

This is the strongest evidence so far that the constraint layer produces genuine
multi-agent capability pressure rather than decoration.

**Infra note:** org TPM limit is 30k -> 429s are routine. Added exponential
backoff + truncation of specialist tool output fed back into context.

---
## [3] SECOND RUN — the Main never asks the specialist that knows

Re-ran 2a163ab_1 with backoff. Crashed on an httpx timeout after retries, but the
transcript before the crash is the point:

    [MAIN -> venmo] "List all Venmo transactions from today involving any of the
                     user's roommates on their Venmo social feed."
    [venmo -> MAIN] "Listed all Venmo transactions from today involving any of
                     the user's roommates on their Venmo social feed."

venmo echoed the request back as if done. It has no address book; it cannot know
who the roommates are. And **the Main never queried `phone` at all** -- it had the
specialist available and never used it. It routed everything to the app that owns
the final action.

**This is the target capability failing, on a real model, on the first two runs.**
gpt-4.1-as-Main does not reason about what each specialist can possibly know. For
RL data that is exactly right: the task is HARD -> there is gradient. Compare
theory-of-mind, which died of 1.0-everywhere.

### Priority correction
The LLM loop is slow (30k TPM, long specialist transcripts). But the forge does
not need an LLM -- the LLM is only needed to VALIDATE that tasks have gradient.
Reordering:
  1. [done] selection/filter -> 51 usable tasks
  2. constraint layer + Harbor packaging  (no LLM)
  3. small validation sweep               (LLM, few tasks)
  4. docs + write-up

### Infra notes for later
- specialists need ~10-14 turns; each turn carries API-doc output -> context grows
- 429s routine; backoff added; httpx timeouts also occur -> need broader retry
- consider a cheaper model for specialists, keep the strong one for Main

---
## [4] SELECTION + CONSTRAINT LAYER BUILT (no LLM needed)

`forge/appworld/select.py` -- the roster comes from the task, never from us.
  - derive_roster() reads apps off the GT, excluding infra apps and the submit
    channel. MIN_ROSTER=2; single-app tasks are dropped, never padded.
  - VERIFIED BOTH WAYS: sabotaging _INFRA_APIS (counting supervisor as a role)
    turns 3 tests red. And on the real 147 GT tasks the module returns exactly
    51/147 -- matching the by-hand measurement.

`forge/appworld/partition.py` -- the constraint layer.
  - Topology: OPEN (control) / STAR (main relays everything) / CHAIN (sub->sub)
  - Visibility: DOCS / NAMES (names-only forces capability discovery to be a
    communication act, which is what makes "who could possibly know this?" a
    reasoning step instead of a lookup)
  - delegation_budget: constraint on the world, never a reward term
  - control_for() is the ablation twin and it is FREE -- same task, same oracle,
    knob off. Every config must beat it or the sub-agents are decoration.
  - Guards: partition on a 1-app roster raises; budget < roster size raises
    (an unsolvable task is noise, not signal).

Suite: 105 passed, 2 xfailed (was 87).

Scale from this alone: 51 tasks x 8 configs = **408 task variants** + 51 controls.
Not by inventing tasks -- by reconfiguring real ones.

### Next
runtime (Main + specialists as proper modules, not prototype scripts), then
Harbor packaging, then the knob-effect measurement that decides which knobs live.

---
## [5] FLOOR EFFECT — the knob measurement is inconclusive, not negative

First sweep rows (task 2a163ab_1, model gpt-4.1 everywhere):
    open-docs-binf    success=False  partial=0.17  deleg=0  turns=16
    star-docs-binf    success=False  partial=0.17  deleg=1  turns=13
    star-names-binf   success=False  partial=0.17  deleg=3  turns=23

All three identical, including the OPEN control -- the unpartitioned condition
where one agent holds every API. **The control fails too.** The task is simply
beyond gpt-4.1.

**A knob's effect is unmeasurable when the control is already on the floor.**
Partitioning cannot make a failing run measurably worse. So this is not evidence
that the knobs are decoration; it is evidence that the measurement was set up
wrong.

### Consequence: a new, mandatory task filter
Only tasks whose OPEN control SUCCEEDS can be used to measure a knob. That filter
cannot be derived by inspection -- it requires real rollouts. It is the same
logic as the G5 gradient gate: all-0 carries as little signal as all-1.

### Model choice
The org has gpt-5.x available (gpt-5.6-luna/sol/terra, gpt-5.5, o3, ...), not
just gpt-4.1. gpt-4.1 was the wrong instrument. Plan:
  - specialists: keep a cheaper model (their job is narrow and mechanical)
  - Main: strong model, so the control can actually succeed
  - then the knob effect is the DROP from a succeeding control
Two model tiers also give the gradient the assignment asks for, for free.

---
## [6] A SILENT-FAILURE BUG IN MY OWN HARNESS — caught by disbelieving a number

Switched the Main to gpt-5.6-sol to break the floor. Result:
    2a163ab_1  OPEN control  success=False partial=0.17 turns=0  9.9s
    2a163ab_2  OPEN control  success=False partial=0.17 turns=0  1.1s
    2a163ab_3  OPEN control  success=False partial=0.17 turns=0  1.0s

`turns=0` and 1 second. The rollout never ran. Cause: **gpt-5.x rejects
`temperature=0`** ("Unsupported value ... Only the default is supported"). Every
call 400'd, `run_one`'s except clause swallowed it into an `error` field I was
not printing, and the row still reported `partial=0.17` -- the score of the
untouched world.

**0.17 is exactly what the failing gpt-4.1 runs reported.** Had I not looked at
`turns`, I would have concluded "the strong model does not help either" and drawn
a real conclusion from a harness bug. This is the project's recurring defect
wearing a new costume: a number that looks like a measurement and is not.

Fixes:
- `chat()` detects the temperature rejection and retries without it, per model.
- the sweep now PRINTS every caught error instead of burying it in a field.
- rows carry `ran` (specialist_turns > 0). A rollout that executed nothing is not
  a rollout; aggregation must drop those rows, never average them in.

Lesson worth keeping for the write-up: the floor effect and the harness bug
produced *identical numbers*. Only a mechanism-level field (`turns`)
distinguished them. Outcome-only logging cannot tell "the agent tried and failed"
from "the agent never ran".

---
## [7] FLOOR BROKEN — the instrument was the problem, and now there is gradient

Same task (2a163ab_1), same OPEN control, only the Main's model changed:

    gpt-4.1      partial=0.17  turns=16   (floor)
    gpt-5.6-sol  partial=0.83  turns=14   ran=True

One number confirms three things at once:
1. The floor-effect diagnosis was right -- the knobs were never the problem, the
   instrument was.
2. **The task has gradient**: 0.17 vs 0.83 across two real models. This is
   exactly what G5 asks for, and exactly what theory-of-mind never had (1.0
   everywhere, both models, every difficulty).
3. Knob effects are now measurable: with the control close to success, the drop
   caused by partitioning means something.

`success=False` at 0.83 matters too -- even gpt-5.6-sol does not fully solve it,
so the ceiling is not pinned either. Signal on both ends.

Model split for the sweep: Main = gpt-5.6-sol (the capability under test),
specialists = gpt-4.1 (narrow, mechanical work). Two tiers also hand the
assignment's multi-model gradient requirement over for free.

---
## [8] KNOB EFFECT MEASURED — the partition passes the anti-toy gate, hard

Task 2a163ab_1, Main=gpt-5.6-sol, specialists=gpt-4.1:

    config             partial  delegations  specialist_turns  wall
    open-docs  (ctrl)   0.83      0            12               95s
    star-docs           0.17      3            39             6704s
    star-names          0.17      6            66            15127s

**The partition is not decoration.** 0.83 -> 0.17 is a 0.66 drop from the single
knob. The sub-agents are the dominant factor in the task's difficulty, which is
exactly what the anti-toy discipline demanded evidence of.

**But the partition saturates.** Both partitioned configs land on 0.17 -- the
floor again, this time caused by the constraint rather than the model. So the
finer knob (visibility: docs vs names) shows **no score difference**, only a
behavioural one: names-only doubled the Main's delegations (3 -> 6) and its
specialists' turns (39 -> 66). The Main worked twice as hard for the same result.

By the stated rule -- a knob that does not move the score is decoration -- the
visibility knob is a delete candidate. The honest reading is narrower: **it is
unmeasurable at this difficulty**, because the partition already put the model on
the floor. Distinguishing "no effect" from "no headroom" needs either an easier
task or a stronger Main. Do not delete it on this evidence; report it as
unmeasured.

**Cost, measured:** one partitioned rollout took 4.2 hours (15127s / 66 turns =
229s per turn). Almost all of that is sleeping in 429 backoff against a 30k TPM
ceiling -- an account limit, not an inherent cost. But it is the real scale
bottleneck for this dimension and the write-up must say so with the number.

### Consequence for what ships
- partition (OPEN vs STAR): measured, large effect -> ships
- visibility (DOCS vs NAMES): behavioural effect measured, score effect
  unmeasurable at this tier -> ships, flagged as unvalidated
- chain topology: still running
- budget: not measured -> do not ship until it is

---
## [9] HARBOR END-TO-END VERIFIED

`harbor run --path tasks/appworld-star-names-binf-2a163ab_1 --agent oracle -n 1`
  trials: 1 | errored: 0
  verifier breakdown: {"success": false, "partial": 0.167, "passes": 1,
                       "failures": 5, "delegations": 0, "ledger": []}

The full chain works: Harbor -> compose sidecar -> AppWorld -> evaluate() ->
reward.txt. `delegations: 0` is correct -- the `oracle` agent deliberately does
nothing (this dimension has no planted solution), so the score is the untouched
world's.

**0.167 matches the 0.17 measured in-process by the knob sweep.** Same oracle,
two paths, same number: containerisation did not change the grading semantics.

### Isolation verified inside the running containers (not asserted)
From `main`:
  team roster                  -> works
  team ask spotify "..."       -> {"error": "you cannot reach 'spotify'"}   (topology enforced server-side)
  curl /state (no token)       -> {"error": "forbidden"}                    (cannot read its own score)
  python -c "import appworld"  -> ModuleNotFoundError                       (no environment in the agent image)
  ls /tests                    -> does not exist                            (no token during the agent phase)
Agent image contains exactly one file: `team`. Leak audit: 0 violations.

### Two real bugs found by running it
1. **psutil needs gcc.** appworld pulls psutil, which has no arm64 wheel on
   python:3.11-slim and compiles. Added build-essential.
2. **Startup race.** Plain `depends_on` waits for the container to start, not for
   the app to be ready. AppWorld's world takes seconds to load, so the verifier
   fired first and reported "cannot reach the sidecar" on a task that was fine.
   Added a healthcheck + `condition: service_healthy`.

Bug 2 is worth keeping: my verifier wrote
`{"error": "verifier failed to reach the sidecar"}` instead of silently
recording 0.0. Without that, a boot race and a genuinely-failing agent would
have produced the same reward and I would have debugged the wrong thing.

---
## [10] TWO REAL BUGS, ONE OF THEM IN MY HEADLINE RESULT

Full sweep: 3 tasks x 4 configs, 12 rows, and it is suspiciously clean --
open=0.833 (min=max), every partitioned config=0.167 (min=max). Zero variance is
a smell, not a triumph. Two things were wrong.

### Bug 1: CHAIN was never implemented
`chain-names` shows `deleg=12` in all three tasks -- exactly `max_steps=12`. All
three answers: `(out of steps)`.

In CHAIN, `allowed_targets("main")` returns only `roster[0]`, so the Main can
reach `phone` and never `venmo`. The handoff `phone -> venmo` has
`allowed_targets(specialist)` defined **and nothing ever calls it**. The topology
is unimplemented: the task is unsolvable and the Main loops to the cap.

Its 0.167 does not mean "chain is harder". It means "chain is impossible". A knob
that scores by breaking the task is worse than decoration -- it is a fake
difficulty signal. Do not ship it.

### Bug 2: my headline number is confounded
The `star` answers are not orchestration failures:
    "Unable to complete: Venmo feed access and roommate identification..."
    "Unable to complete: Venmo cannot access the social feed"
    "Unable to complete: phone contact search and Venmo social-feed unavailable"
**The specialists are refusing.** And the specialists are gpt-4.1 while the OPEN
control's work is done by gpt-5.6-sol.

So `0.83 -> 0.17` changes TWO things at once:
  (a) the Main loses direct access  <- what I claim to measure
  (b) the API work is now done by a weaker model  <- confound

The anti-toy gate I was so pleased to have passed does not cleanly separate
"partitioning is hard" from "gpt-4.1 cannot drive venmo". Note the GT for these
tasks uses `venmo.show_social_feed`, so the API exists -- the specialist failed
to find or use it.

**Decisive experiment running:** star + gpt-5.6-sol specialists. If it stays at
0.167 the partition is the cause; if it rises, the confound is real and the
headline needs rewriting.

This is the same disease as everything else in this project: a number that looked
like a measurement of the thing I cared about, and was partly a measurement of
something else. Zero variance should have made me suspicious immediately.

---
## [11] CONFOUND REFUTED — the partition owns the drop

star with gpt-5.6-sol specialists (same model as the control's worker):
    2a163ab_1  star+strong-subs  partial=0.167  deleg=2
    2a163ab_2  star+strong-subs  partial=0.167  deleg=2

Identical to the gpt-4.1-specialist runs. Upgrading the specialists to the
control's own model changes nothing, so the 0.83 -> 0.17 drop belongs to the
partition, not to (b) the weaker model. Headline stands, now with the confound
tested rather than assumed.

The upgrade changed only the failure mode:
    gpt-4.1 specialists:     "Unable to complete: Venmo cannot access the social feed"
    gpt-5.6-sol specialists: "No Venmo social-feed transactions from today involving my roommates"
The control scores 0.83, so the transactions exist. **A stronger specialist did
not rescue the task -- it converted a refusal into a confident wrong answer.**
That is the failure that matters for orchestration: an agent told "there is
nothing there" by a competent-sounding specialist has no way to know it asked
the wrong one. Same shape as the venmo-hallucinates-roommates finding on run one.

## [12] SABOTAGE-VERIFIED THE THREE DISCIPLINES

Green tests prove nothing; only breaking the guarded property does.
    supervisor counted as a role      -> 3 tests red
    topology not enforced             -> 1 test red
    chain re-added to SHIPPED_CONFIGS -> 1 test red
Restored: 118 passed, 2 xfailed.

## SESSION SUMMARY

Built, on branch feat/appworld-orchestration:
- forge/appworld/{select,partition,runtime,harbor,cli}.py + container/
- 42 new tests (76 -> 118), all sabotage-verified
- 4 Harbor tasks rendered, agent image = 1 file, leak audit clean
- docs/APPWORLD_DESIGN.md (the brief's 5 questions), WRITEUP.md, README rewritten

Verified end-to-end in real containers:
- harbor run --agent oracle -> verifier pulls AppWorld's verdict from the
  sidecar: partial=0.167, matching the in-process sweep exactly
- from inside `main`: topology refuses off-roster specialists, /state 403s
  without the token, `import appworld` raises ModuleNotFoundError, /tests absent

Measured:
- 51/147 tasks usable (naive filter would say 147/147)
- partition 0.833 -> 0.167 (n=3), confound refuted with strong specialists (n=2)
- model gradient on the control: gpt-4.1 0.17 vs gpt-5.6-sol 0.83
- cost: 4.2h per partitioned rollout, nearly all 429 backoff

Found and reported rather than buried:
- chain was never implemented; its 0.167 was the step cap. Unshipped.
- the headline was confounded; tested it; the confound lost.
- gpt-5.x rejects temperature=0 -> every call 400'd, was swallowed, and reported
  the untouched world's score (0.17) -- the same number the real failures gave.
- the naive task filter would have shipped 96 single-app puzzles with a
  decorative second agent.

STILL RUNNING at handoff: harbor run with terminus-2/gpt-5.6-sol (a real LLM Main
in the container, rather than the no-op oracle agent). The sidecar path is
already proven by the oracle run; this would show a real agent driving it.

OPEN / NOT DONE:
- chain handoff (specialist -> specialist) is defined and uncalled
- delegation budget knob unmeasured, unshipped
- finer knobs need an easier task or a stronger Main to become measurable
- knob table is 3 tasks x 1 seed

---
## [13] THE 0.833 CEILING WAS MINE — every number was capped

The user asked three times why the scores were identical and what full marks
even means. Each ask went one layer deeper. The third one found a real bug.

Printing the six requirements individually (I had only ever looked at the
aggregate "5 pass / 1 fail"):

    PASS  assert no new venmo.Transaction was added        <- free when you do nothing
    FAIL  assert answers match
    FAIL  assert model changes match venmo.Transaction, venmo.TransactionLike
    FAIL  assert set of all new transaction likes is identical to ...
    FAIL  assert all newly liked transaction_ids are in recent_transaction_ids
    FAIL  assert all newly liked transaction_ids are in relative_transaction_ids

So do-nothing = 1/6 = **0.167**. That is where that number comes from.

The GT for this task ends `return None` -- it is an ACTION task, and its answer
is None. **My harness always submits a prose string.** Measured directly:

    same work, prose answer  -> success=False  partial=0.833 (5/6)
                                still failing: "assert answers match"
    same work, answer=None   -> success=True   partial=1.000 (6/6)

**0.833 was my harness's ceiling, not the task's.** Consequences:
- every action task in every sweep was silently capped at 5/6
- `success=True` was NEVER reachable through my pipeline
- WRITEUP said "0.83 is not 1.0: the ceiling is not pinned either" -- that
  sentence is FALSE. I had welded the ceiling shut myself.

Fixed: `_as_answer` in server.py and `_is_action_answer` in the sweep now submit
None when the Main reports an action. The instruction already told the Main to
say `completed` for action tasks; the harness just ignored it.

Re-measuring the knob sweep now. Every number in the docs is suspect until it
lands.

This is the fourth instance in this session of the same disease: a number that
looked like a measurement of the task and was partly a measurement of my own
harness. The tell was available the whole time -- I just never printed the
per-requirement breakdown.
