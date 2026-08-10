# Task-pool expansion — design

**Date:** 2026-08-10. **Status:** approved design, pre-implementation.
**Companion:** `2026-08-08-genjob-orchestrator-design.md` (the orchestrator
this spec sequences and slices; that doc's decisions stand except where
amended below).

## Why this exists

After the v4/v5 seeds and their fixes, the study's bottleneck moved from the
harness to the task pool. The informative population is 3 scripted-judge
scenarios; cell outcomes replicate exactly across seeds (12/12), so more
seeds of the same cells buy confirmation, not information. Worse, the three
abilities on the masthead are barely exercised: capability-discovery went
6/6 across two seeds (the knob never bites), and context-transfer's only
failures were delegation *timing*, not brief content. More tasks are needed
in two senses: more scenarios that the deterministic judge can grade, and
new task families designed so each ability is load-bearing by construction.

## Decisions (made 2026-08-10)

1. **Both sources, staged.** Widen the inherited Gaia2 pool first (free,
   days); build the generation-job orchestrator second (the real
   instrument).
2. **Charters: agent-drafted, Michael-owned.** Amends the orchestrator
   design's decision 4 ("charters are written by Michael. No agent-proposed
   charters") to: charter *drafts* may be agent-written; a charter has no
   effect until Michael personally runs `forge.factory queue` on it, and
   that act is the approval. The human gate survives; the blank page does
   not.
3. **Build order: widen, then thin slices.** The orchestrator lands in four
   offline-tested milestones rather than one push; the first real charter
   runs as soon as stages 1–2 work.

## Part A — widen the inherited pool

### A1. Roster completion (rescue the 4 blind scenarios)

Today `roster_blind_facts()` (forge/gaia2/mine.py) finds facts the gold
writes consume that only off-roster apps hold, and admission *excludes* the
scenario. The same evidence names the repair: the fact's `sources` are
exactly the apps the roster is missing.

Change: `derive_roster()` gains a completion pass — after the write-apps and
seam-sources union, compute blind facts against that provisional roster and
add every `BlindFact.sources` app. Recorded honestly: `Gaia2Span` gains
`roster_completed: tuple[str, ...]` naming the added apps (empty for the 33
clean scenarios, whose rosters must remain byte-identical — pinned by a
test). `roster_blind` is computed against the completed roster; the
admission/eligibility/render gates all stay, catching any future scenario
where completion cannot identify a provider (no candidate app, or more than
`MAX_SEAM_SOURCES` — ambient facts complete nothing).

Expected effect, measured 2026-08-10 against the current pool:

| scenario | roster gains | judge |
|---|---|---|
| scenario_universe_24_tg3h3h | Files | scripted |
| scenario_universe_22_bt12gw | Contacts, InternalContacts | scripted |
| scenario_universe_21_y6td7z | Messages | soft |
| scenario_universe_21_5flf8t | Messages, Chats | soft |

Scripted pool 3 → 5 (20 cells/seed). Comparability: the four rescued
scenarios were never in any campaign's informative population (they were
excluded or structurally lost), so no historical number changes meaning;
the next campaign takes a new label regardless (the v6 prompt changes
already force one).

Evidence: admission probes re-run for both fetched splits; the campaign
`--dry-run` must show 20 scripted cells; `sweep/gaia2_*_admission.json`
gains the `roster_completed` field.

### A2. Fetch and measure the four unfetched splits

`scripts/gaia2_fetch.py` knows six splits; only `mini` and `adaptability`
were ever fetched. Fetch `ambiguity`, `execution`, `search`, `time`
(parquet download, no model cost), run the admission probe on each, dedupe
by `scenario_id` against the known pool, and report per split: total,
usable, seamful, script-judgeable (not reply-conditioned), roster-blind
(should be zero after A1 completion — any nonzero is a new finding).

Deliverable: `sweep/gaia2_<split>_admission.json` per split plus a summary
table in the run report. **No paid episodes** — the seed on the widened
pool is a separate, explicitly approved spend.

### Out of scope for A

Re-mining seams with containment matching everywhere (it can reclassify
facts as ambient and shrink existing seams — a full re-measurement, not a
widening), soft-judge calibration, and the control step-cap asymmetry.
Each is a separate decision.

## Part B — three charters, drafted for Michael's ownership

Three charter drafts, one per ability, each shaped so the ability decides
pass/fail and the known confounds cannot:

* **capability-discovery**: solvable only by working out *which* role can
  know a required fact (information placed so no roster listing reveals
  it); explicitly no deadline pressure — non-goal: timing.
* **context-transfer**: the brief's content decides — the fact set needed
  by the executing role is large enough that a vague brief measurably
  fails, with the counterfactual that a full-information single agent
  solves it trivially; non-goal: discovery difficulty (roster is obvious).
* **delegation-economy**: over-delegation is fatal by construction (each
  round-trip consumes a bounded resource other than wall-time, so the cost
  is the *count*, not the clock); non-goal: hiding information.

Each draft carries the orchestrator charter fields: one-sentence capability
claim, falsifiable counterfactual, non-goals, optional budget override.
Drafts land as `genjobs/<date>-<slug>/charter.md` with `status: draft` in
front-matter; `forge.factory queue` refuses drafts, and Michael's edit
removing the marker plus running `queue` is the approval act (decision 2).

Charters are written against `skills/build-ground-up-multi-agent-tasks/
SKILL.md` stage 1 and reviewed by its blinded provenance reviewers once the
orchestrator can run them — the drafts do not shortcut any stage.

## Part C — forge/factory in four milestones

The orchestrator design doc stands in full (layout, state machine, session
harness, gate table, cost control, non-goals). This spec only slices the
build:

* **M1 — state.** `forge/factory/` package: `state.json` schema +
  atomic-write transitions as pure functions, `queue` (charter validation,
  branch + worktree creation), `status`, `abandon`. All transition logic
  fixture-tested offline; no session code.
* **M2 — sessions and the front half.** The `claude -p` session harness
  (stream-json capture, result extraction, per-role tool scoping),
  instruction composer with golden-render tests, stages 1–2 with their gate
  checkers, `awaiting-spec-approval` parking, `approve --spec`. Integration
  test drives a job to the spec gate against a fake `claude` binary. The
  first real charter may run at M2 — its output is a human-reviewed task
  contract, cheap and informative.
* **M3 — the build stages.** Gate checkers for stages 3–8 (import-graph
  check, determinism re-run, counterfactual suite, instance validation,
  mutation matrix, usefulness report). Fixture-driven pass/fail tests per
  checker.
* **M4 — independence and delivery.** Blinded review directories (stage 9),
  clean-room clone and `validate.sh` (stage 10), `approve --release`,
  stage-9 reopen logic, `stuck`/budget parking. End-to-end fake-binary test
  through both human gates including a retry and a reopen.

Each milestone merges only with its tests green and offline (the design
doc's testing section is the contract); no milestone requires API spend to
test. First paid session happens when Michael queues a charter after M2.

## Testing summary

* A1: TDD in `forge/tests/test_gaia2_mine.py` — completion adds exactly the
  measured apps for the 4 fixtures/real scenarios; clean scenarios'
  rosters byte-identical; gates still refuse an uncompletable fixture.
* A2: fetch is an existing script; the admission probe's numbers are the
  test (deterministic, committed as evidence).
* B: charter drafts are prose; the `queue` refusal of `status: draft` is
  TDD'd in M1.
* C: per the orchestrator doc — state-machine fixtures, golden renders,
  checker fixtures, fake-binary integration. No API calls in any test.

## Risks

* **Completion legitimizes a mis-mined roster** (adds an app the task
  didn't really need): bounded by the same guards as blindness detection
  (containment length floor, ambient cap, given-text exclusion), and the
  added app is recorded in `roster_completed` + admission evidence, so a
  reviewer can audit every completion.
* **The new splits are duplicates or soft-judge-only**: the measure-first
  step costs nothing; if yield is poor, Part B/C carry the pool.
* **Charter drafts anchor Michael** (agent framing narrows his design):
  mitigated by drafts carrying explicit alternatives sections and by the
  stage-1 blinded provenance review, which exists to catch precisely
  inherited framing.

## Sequencing

A1 → A2 (same branch, one PR) → B drafts (parallel, prose only) → C
milestones M1–M4 in order. The next paid seed (widened pool, v6 label,
prompt changes included) is its own go/no-go after A lands.
