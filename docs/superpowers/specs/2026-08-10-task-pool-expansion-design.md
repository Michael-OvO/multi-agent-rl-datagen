# Task generation system — design

**Date:** 2026-08-10 (revised same day: generation-first, dashboard in
scope, brainstorm pathway added). **Status:** approved design,
pre-implementation.
**Companion:** `2026-08-08-genjob-orchestrator-design.md` — the orchestrator
core. Its decisions stand except where the amendments below say otherwise.

## Why this exists

The study's bottleneck is the task pool: 3 informative scenarios, abilities
not load-bearing, outcomes replicating exactly across seeds. Michael's
direction (2026-08-10): **build the generation flow first, then use it to
enlarge and deepen the banks.** The generation system is the product; task
banks are its output. Four requirements, verbatim intent:

1. CLI **and** UI viewer — the dashboard the orchestrator doc deferred is
   now in scope.
2. Multiple pathways to brainstorm and generate.
3. A grid view where jobs and their agents are visible and manageable in
   real time.
4. Measurable, clear, accurate task-generation status and quality
   indication.

## Amendments to the 2026-08-08 orchestrator design

1. **Dashboard is in scope** (supersedes its non-goal 1). It is the
   *factory board*, component 2 below.
2. **Decision 4 amended** (recorded 2026-08-10, reaffirmed): charter drafts
   may be agent-written — by hand or by the brainstorm pathway — but a
   charter has effect only when Michael queues it. The queue action is the
   ownership act.
3. **Decision 3 extended, not broken:** one job type, plus an approved
   family may later re-enter at stage 6 for instance deepening (stages 7–8
   re-validate). Deepening and variation pathways are **deferred** until
   the first family ships; the design leaves room, builds nothing.

Everything else in the orchestrator doc — layout, lifecycle, stage table,
session harness, state.json, cost control, risks — stands unmodified and is
not restated here.

## Components

### 1. `forge/factory` — the orchestrator core

Exactly per the 2026-08-08 doc, plus one addition: a **command inbox**. The
orchestrator's run loop polls `genjobs/<job>/commands/` for single-action
JSON files (`approve-spec.json`, `approve-release.json`, `retry.json`,
`abandon.json`, `queue.json`), executes each against the same code paths as
the CLI verbs, and moves the file into `commands/done/` with the outcome
appended. This is the entire bridge the UI needs — the board writes files,
the orchestrator does everything else. CLI verbs keep working identically;
a command file records `"by"` from the charter's `owner` field so approvals
stay attributable.

### 2. `factory_board.html` — the snapshot board

A second single-file, no-server, offline HTML surface (PRODUCT.md's
constraints apply: self-contained, no build step, no network, truthful).

**Loading model — corrected 2026-08-10.** An earlier draft of this spec
said the board would folder-connect and live-read, and offered that as the
repo-native choice. That was wrong: `trajectory_viewer.html` had a File
System Access layer and it was **deliberately retired** in `f3c66bc`
(2026-07-28) — *"Opening the file is the whole workflow again, with no
permission prompt in front of it."* The board therefore follows the
committed loading model, the embedded snapshot:

* `python -m forge.factory.cli board` renders `genjobs/board.html` with the
  whole queue's state embedded as a JSON blob, exactly as
  `scripts/embed_logs.py` does for the viewer;
* the orchestrator's run loop re-renders it after every state transition,
  so the file on disk is never more than one transition stale;
* the page reloads itself on a timer (default 5s, a visible control to
  pause), giving near-real-time without a permission prompt, a server, or
  the retired API. The rendered `updated` timestamp is always on screen, so
  a stopped orchestrator reads as stale rather than as live.

Embedded per render: every `genjobs/**/state.json`; each attempt's
`check.json` and `result.json` summary; the **tail** of each running
attempt's `transcript.jsonl` (bounded, e.g. last 200 lines — transcripts
are gitignored and can be large); and the `ideas/*.md` front-matter for the
inbox.

**Managing is CLI-side.** The board renders, for every actionable job, the
exact command to run (`python -m forge.factory.cli approve <job> --spec`)
with a click-to-copy affordance. It writes nothing — no browser write
capability has ever existed here, and inventing one would mean reviving the
retired permission flow. The command inbox (component 1) still exists for
future non-CLI clients but is not exercised by the board in this scope.

**Grid view (requirement 3).** Rows = jobs, columns = the ten stages. Each
cell shows that stage's state: pending / running (with elapsed time and
live session count) / gate-passed / gate-failed (attempt n of cap) /
parked-for-human / reopened. Row header: job slug, status, spend vs budget.
Clicking a running cell opens the transcript tail; clicking a finished cell
opens its `check.json` verdict and artifacts.

**Manage affordances.** For each job needing a human, the board shows the
verbatim CLI command and a copy control — approve spec, approve release,
retry, abandon, queue a draft charter, promote an idea. The board asserts
nothing about the outcome; the next render shows what actually happened.

**Quality panel (requirement 4).** Per job, numbers read verbatim from the
stage artifacts the skill already mandates — never computed by the board:

| indicator | source |
|---|---|
| ambiguity findings / resolved | stage 2 reviewer records + reconciliation |
| implementation independence | stage 3 import-graph check verdict |
| determinism | stage 4 replay hash comparison |
| collaboration necessity | stage 5 counterfactual suite (control / reference / role-removal) |
| instance yield + rejection reasons | stage 6 validation report |
| mutation kill rate, critical mutants | stage 7 `mutation-report.json` |
| floor / control / reference / constrained gaps | stage 8 `run-report.json` |
| review findings by severity + dispositions | stage 9 records |
| clean-room validation | stage 10 verdict |

A job's headline quality line is the *worst unresolved* indicator, named —
not a composite score (composites hide exactly the thing the reader needs;
same rule as the trajectory viewer's verdict handling).

**Design system.** The board joins the repo's committed visual world,
which is **DESIGN.md's overview-over-tables dashboard** — status carried by
colour, icon, and word at once. The proceedings/booktabs evidence page was
overturned on 2026-07-28 and must not be revived; the phrase survives as
stale copy in `PRODUCT.md:24` and in an earlier draft of this spec, and
`.impeccable/design.json` is a pre-reversal artifact that must not be read
as the design system. Concretely the board obeys: the committed ground-and-
ink tokens by name and hex in all three theme scopes; the three-value
status roles (mark for non-text at 3:1, `-ink` for text at 4.5:1, `-tint`
for fill that never carries alone); one `badge(kind, label)` builder
emitting colour + icon + word with `aria-hidden` on the glyph; a legend
above the stage grid keyed for every stage state including `— not run`;
missing data drawn as explicit absence, never inferred; one centred 1080px
column with the grid scrolling inside its own panel.

### 3. The brainstorm pathway

`python -m forge.factory brainstorm --n N [--theme "..."]` spawns N
concurrent headless sessions, each producing one idea file:

```
ideas/<slug>.md
---
status: idea
proposed: <timestamp>
session: <session-id>
---
# <capability name>
**Pitch.** (one paragraph)
**Capability claim.** (one sentence, the charter's future seed)
**Falsifiable counterfactual.** (what result would disprove it)
**Why the current bank cannot measure this.** (grounded in the study)
**Sketch.** (roster shape, what the verifier would check — non-binding)
```

Idea sessions are cheap (one session, no tools beyond read access to the
skills and the study's evidence files, bounded tokens). The board's inbox
lists ideas; **promote** writes `genjobs/<date>-<slug>/charter.md` with
`status: draft` pre-filled from the idea — still inert until Michael queues
it. Ideas never build anything; the pathway ends at a draft charter.

Duplicate pressure is handled at promotion, not generation: the inbox
shows, next to each idea, the existing charters/families with overlapping
capability claims (substring/keyword match — honest and dumb), and the
human decides.

### 4. Status and quality model (requirement 4, the data side)

`state.json` remains the single source of job status (orchestrator doc's
schema). The board derives, never stores. Two additions to the orchestrator
core to make status *accurate in real time*:

* the session runner touches `attempts/<stage>-<n>/heartbeat` (mtime-only)
  every poll interval while a session lives, so the board can distinguish
  "running" from "crashed orchestrator" without a server;
* `state.json` gains `"updated"` (timestamp of last transition), already
  implied by atomic writes, now explicit.

## Milestones (generation-first order)

* **M1 — state + queue.** `forge/factory` package: state machine as pure
  functions, `queue` (validates charter, refuses `status: draft`), `status`,
  `abandon`, atomic writes, fixtures. Offline tests only.
* **M2 — board v1, read-only.** `cli board` renders `genjobs/board.html`
  from a job tree, plus the grid, quality panel, and self-refresh. Built
  and tested against the **fixture** tree M1's tests already use, so the
  board is complete before any session exists.
* **M3 — sessions + the front half.** Session harness (per the
  orchestrator doc), stages 1–2 with gate checkers, `awaiting-spec-approval`
  parking, the command inbox, `approve --spec`; board gains manage buttons.
  Fake-`claude` integration test to the spec gate.
* **M4 — brainstorm pathway.** `brainstorm` verb, idea files, board inbox +
  promote. First real spend possible here (idea sessions), at Michael's
  explicit go.
* **M5 — build stages.** Gate checkers 3–8; board quality panel fills in.
* **M6 — independence + delivery.** Stages 9–10, blinded directories,
  clean room, `approve --release`, reopen logic; end-to-end fake-binary
  test; first family ships.

Charters: the three ability drafts already written
(`genjobs/2026-08-10-*/charter.md` per the implementation plan) queue as
soon as M3 exists.

## The inherited-pool track (background, does not gate the factory)

Part A of the pre-revision spec (roster completion; fetch + measure the
four unfetched splits) stays approved with its plan already written
(`docs/superpowers/plans/2026-08-10-task-pool-expansion.md`, Tasks 1–4). It
is free, small, and independent; it runs whenever convenient. The paid v6
seed on the widened pool remains its own go/no-go and should wait for that
track so the seed prices 20+ cells.

## Testing

Per the orchestrator doc (state fixtures, golden renders, checker
fixtures, fake-`claude` end-to-end), plus:

* the board is developed and tested against the same committed fixtures the
  state-machine tests use — a fixture tree under
  `forge/tests/fixtures/factory/` is the board's data contract;
* `forge/tests/test_factory_board.py` follows `test_viewer.py`'s
  hand-written-source assertion style (the repo already knows how to test
  a single-file HTML surface);
* command-inbox round-trip: a command file fixture in, state transition +
  `done/` outcome out, pure function.

## Risks beyond the orchestrator doc's

* **The board shows stale state as live** (no server to push): mitigated by
  the heartbeat files and by always rendering the `updated` timestamp;
  "last change 4m ago" is honest where a green dot would lie.
* **Brainstorm floods the inbox with plausible duplicates**: bounded by
  `--n`, the overlap listing at promotion, and the human promotion gate.
* **UI scope creep** (the board becoming an editor): the board writes
  command files and nothing else; charters are edited in the editor, not
  the browser. Non-goal, stated here.

## Sequencing

M1 → M2 → M3 → M4 → M5 → M6, with the inherited-pool track interleaved at
will. First writing-plans session covers M1 + M2 (they share fixtures).
Deepen/variation pathways return as a new spec after the first family
ships.
