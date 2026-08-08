# Generation-job orchestrator — design

**Date:** 2026-08-08. **Status:** approved design, pre-implementation.

## What this is

An autonomous pipeline that turns a human-written capability charter into a
complete, independently audited multi-agent task family, by driving headless
Claude Code sessions ("headless" = the same `claude` command-line tool launched
by a program via `claude -p`, running its agent loop to completion without an
interactive terminal; it runs locally and bills the Anthropic API) through the
ten stages of `skills/build-ground-up-multi-agent-tasks/SKILL.md`. A companion
dashboard that visualises these jobs is a **separate, later sub-project**; it
will read the `state.json` files this orchestrator writes, the same way
`trajectory_viewer.html` reads rollout artifacts today.

Decisions fixed during brainstorming, in order:

1. Orchestrator first; dashboard second, against real artifacts.
2. Agent runtime: Claude Code headless (not the pi coding agent, not a
   hand-rolled API loop).
3. One job type only: **ground-up task families** per
   `build-ground-up-multi-agent-tasks`. No fix/debug jobs, no
   substrate-admission jobs, no sweep-wrapping jobs.
4. Charters are written by Michael. No agent-proposed charters.
5. Two human gates: after stage 2 (the written task contract) and at the
   release decision after stage 10.
6. Architecture: filesystem-native (job = directory, orchestrator = resumable
   command-line tool). No server, no database, no GitHub coupling.

## Why this exists

The skill demands things an interactive session cannot honestly provide:
two *blinded* ambiguity reviewers who did not author the task (stage 2), four
independent review passes with fresh context (stage 9), and a clean-room
operator distinct from the author (stage 10). One person driving one Claude
Code session cannot produce genuinely independent principals. An orchestrator
that spawns a **fresh headless session per role**, each seeing only the files
its role is allowed to see, enforces principal separation mechanically and
records it verifiably.

## Layout

New pieces only; nothing existing changes.

```
forge/factory/            the orchestration package (library + command-line
                          interface, invoked as `python -m forge.factory`)
genjobs/                  the queue: one directory per job (committed, minus
                          transcripts)
families/                 approved task-family packages land here, via a
                          human merge — never an orchestrator merge
```

### A job directory

```
genjobs/<YYYY-MM-DD>-<slug>/
  charter.md              written by Michael; `forge.factory queue` turns the
                          directory into a registered job
  state.json              owned by the orchestrator after `queue`
  attempts/<stage>-<n>/   per (stage, attempt):
    instructions.md       the exact composed prompt the session received
    result.json           the session's structured result (from
                          --output-format stream-json, final message + usage)
    check.json            the deterministic gate checker's verdict
    transcript.jsonl      raw session stream — gitignored
```

`charter.md` holds the skill's stage-1 seed: a one-sentence capability claim,
the falsifiable counterfactual, non-goals, and optionally a per-job token
budget override.

The family under construction lives on branch `genjob/<slug>`, checked out in
a git worktree under the machine-local scratch area (worktrees are never
inside the repository tree and never committed). Parallel jobs cannot touch
each other or `main`.

## Lifecycle

`state.json` carries a stage cursor (1–10, mapping one-to-one onto the
skill's stages) and a status:

```
queued -> running -> awaiting-spec-approval -> running ->
awaiting-release-review -> shipped | quarantined | blocked
any running state -> stuck (attempt cap or budget cap exhausted,
                            or a gate check needs a human)
any state -> abandoned (human decision)
```

Per stage, the orchestrator:

1. composes the stage instructions (see Session harness);
2. spawns the stage's session(s) — sessions the skill declares independent
   (the two ambiguity reviewers, the four stage-9 reviews) run concurrently;
3. runs the **deterministic gate check** itself. The agent never grades its
   own stage; a session claiming success changes nothing.

Gate check passes → cursor advances. Fails → the stage is re-queued with the
check's failure output prepended to the next attempt's instructions, up to
`attempts_per_stage` (default 3). Infrastructure failures (session crash,
API error) are a separate outcome category and do not consume a gate attempt
— mirroring the skill's infrastructure-versus-policy distinction. Exhausting
the attempt cap or the job token budget parks the job as `stuck`.

Human gates are parking states:

* after stage 2 the job stops at `awaiting-spec-approval`; Michael reads the
  task contract and the ambiguity-review reconciliation, then runs
  `python -m forge.factory approve <job> --spec`;
* after stage 10 the job stops at `awaiting-release-review` carrying the
  skill's release decision (`READY` / `QUARANTINED` / `BLOCKED`). Approving a
  `READY` verdict means **Michael merges** the `genjob/<slug>` branch so the
  family package lands in `families/<slug>/`. The orchestrator never merges.

A stage-9 critical finding reopens the earlier gate the skill names: the
orchestrator resets the cursor to that stage and the loop resumes.

## Stage table

| # | skill stage | session principals | deterministic gate check (run by the orchestrator) |
|---|---|---|---|
| 1 | Charter the capability | author; two blinded provenance reviewers | charter fields complete, no placeholders; two provenance-review records from distinct session IDs in `audit/design-provenance.json` |
| 2 | Specify the task | author; two blinded ambiguity reviewers; author reconciles | `task-spec.json` parses with no placeholders and complete requirement IDs; two reviewer write-set outputs from distinct session IDs; reconciliation recorded → park at `awaiting-spec-approval` |
| 3 | Three independent implementations | author | `generator/`, `solution/`, `verifier/` present; static import-graph check that the verifier imports no generator decision logic and the solution calls no verifier helpers; unit tests pass |
| 4 | World replay and diagnosis | author | orchestrator runs the generator twice with one seed and compares state hashes; a sample episode's event log carries every field the skill lists |
| 5 | Collaboration necessity | author | the counterfactual suite runs green: control solves, reference team solves, each role-removal breaks a named requirement, boundary/leak test passes |
| 6 | Instance generation | author | instance-validation report present with admitted count, rejection reasons, and yield; duplicate detection ran |
| 7 | Verifier validation | author | machine-readable mutation matrix (`audit/mutation-report.json`) with **all critical mutants killed**; do-nothing, random-valid, greedy, and exploit policies ran with expected failures |
| 8 | Task usefulness | author | `audit/run-report.json` contains floor, unconstrained control, reference, and constrained-team measurements; floor < reference; not saturated, not floored |
| 9 | Independent review | four reviewers (spec, verifier, red-team, operator-dry-run), all blinded per the skill | four review records from four distinct session IDs with blinding manifests; every finding dispositioned; critical findings reopen the named stage |
| 10 | Package and delivery | clean-room operator (fresh `git clone` of the job branch into scratch; operator session ID distinct from every author session ID) | `validate_task_package.py` passes; `validate.sh` exits 0 in the clean room; release decision recorded → park at `awaiting-release-review` |

Gate checks validate the **evidence shapes the skill already mandates**
(`references/audit-schemas.md`); this design invents no new audit format.

## Session harness

Each session is one `claude -p` subprocess:

* working directory = the job worktree, **or** a bare review directory for
  blinded roles containing only the files that role may see (blinding is
  enforced by the filesystem, not by instruction), **or** the clean-room
  clone for stage 10;
* `--output-format stream-json`, captured whole to `transcript.jsonl`;
  final result and token usage extracted into `result.json`;
* tool permissions scoped per role: reviewers read-only; author sessions get
  edit + Bash confined to the worktree; the operator gets Bash in the clone;
* prompt composed from three layers: a role frame ("you are the verifier
  reviewer; you did not author this task"), the stage's instruction template
  quoting the relevant `SKILL.md` section, and — on retries — the previous
  attempt's `check.json` failure verbatim;
* model pinned per stage in one configuration table; default is one model
  everywhere.

Session IDs are stamped into the audit files as the principal records the
skill requires (author principal, reviewer principals, operator principal).

## state.json

```json
{
  "job": "2026-08-08-hidden-dependency-scheduling",
  "created": "2026-08-08T14:00:00-07:00",
  "status": "running",
  "stage": 4,
  "branch": "genjob/hidden-dependency-scheduling",
  "worktree": "/path/to/scratch/worktrees/hidden-dependency-scheduling",
  "caps": { "attempts_per_stage": 3, "total_tokens": 20000000 },
  "spend": { "total_tokens": 1234567, "sessions": 9 },
  "attempts": [
    {
      "stage": 2, "attempt": 1, "role": "author",
      "session_id": "uuid", "model": "model-id",
      "started": "2026-08-08T14:03:11-07:00",
      "ended": "2026-08-08T14:19:47-07:00",
      "tokens": 123456,
      "outcome": "gate-passed",
      "check": "attempts/2-1/check.json"
    }
  ],
  "approvals": { "spec": { "by": "michael", "at": "..." }, "release": null },
  "release_decision": null
}
```

Written atomically (write-temp-then-rename) after every transition; all
timestamps timezone-aware. Kill the orchestrator at any point and relaunch;
it resumes from `state.json` — the same resumability contract as
`scripts/gaia2_campaign.py`.

## Command-line interface

```
python -m forge.factory queue <charter-dir>    validate charter, init state,
                                               create branch + worktree
python -m forge.factory run [--job X] [--workers N] [--dry-run]
python -m forge.factory approve <job> --spec | --release
python -m forge.factory abandon <job>
python -m forge.factory status
```

`run` processes every runnable job (default sequential; `--workers` for
parallel jobs); `--dry-run` prints the work plan and prices nothing.

## Cost control

Token usage is read from each session's result and accumulated per job.
The budget cap comes from `charter.md` when set, else a repo-level default in
the factory configuration. Exceeding it parks the job `stuck` with the spend
recorded — never a silent stop.

## Testing (all offline, `forge/tests/`)

* state machine: pure-function transition tests over `state.json` fixtures;
* instruction composer: golden-render tests for every stage and role;
* gate checkers: passing and failing fixture audit files for each stage;
* integration: a fake `claude` binary (a script emitting canned stream-json)
  drives one job end-to-end through both human gates, including a gate
  failure and retry, a `stuck` path, and a stage-9 reopen. No API calls in
  any test.

## Non-goals

* No dashboard in this sub-project. The dashboard is the next spec; its data
  source is `genjobs/**/state.json` plus attempt artifacts, read the way the
  viewer reads rollouts.
* No agent-proposed charters.
* No job types other than ground-up task families.
* No server, no database, no remote execution.
* The orchestrator never merges to `main` and never writes outside
  `genjobs/`, the job worktrees, and the scratch area.

## Risks and mitigations

* **A session games a gate check** (writes the evidence file without doing
  the work): mitigated where it matters most by checks that *execute* rather
  than read — the determinism check reruns the generator, stage 10 reruns
  `validate.sh` in a clean room, mutation results must name the mutants. The
  skill's own warning applies: reports establish traceability, not truth;
  the release gate stays human.
* **Retry loops burn budget on a doomed charter**: the spec-approval gate
  exists precisely to kill doomed charters after stage 2, before the
  expensive build stages; attempt caps and the token budget bound the rest.
* **Blinding leaks through the repo itself** (a reviewer session reads the
  author's files): blinded sessions run in bare directories outside the
  worktree with read-only tools; the review directory's manifest is recorded
  in the audit file so a leak is at least detectable.
