# The viewer tracks every result itself: index, auto-refresh, and the truth about Gaia2

Date: 2026-08-31
Status: approved design (revised once), pending spec review

## Context

`trajectory_viewer.html` is the repository's single visual surface, and its
whole loading model is a JSON snapshot embedded in the page (`#embedded-logs`),
plus drag-and-drop and a file picker. That snapshot was last generated on
2026-07-28 16:20 and is refreshed only when someone remembers to run
`scripts.embed_logs`. It carries 239 files: the `full` campaign's 173
episodes, 20 probe episodes, and seven Gaia2 evidence files. Nothing from v3,
v4, v5 or v6 is in it. No embedded episode carries a `judge_parse` stamp or an
instrumented `stop` row, because both were added after it was generated.

Since then the repository learned three things the page cannot currently say:

1. **The Gaia2 soft judge's zero was a parse defect.** Its checker model
   answers `[[true]]`; the judge matched `[[True]]` case-sensitively, recorded
   the unreadable answer as a rejection, and scored 0 of 492 across five
   campaigns. `forge/gaia2/judge_parse.py` (commit `0a83ccf`) reads the
   sentinel without regard to case; every trajectory now stamps
   `judge_parse: case-insensitive-v1`; `sweep/gaia2_v6_judge_parse.json`
   measures 3 of 30 passing under the stock parse and 26 of 30 under the fix.
   Every soft-judge verdict the page currently shows predates the fix.
2. **Why an episode ended is now recorded.** Every `stop` event carries the
   world's `reason`, `duration`, `time_passed`, `remaining` and `env_state`
   (commit `a59d9bb`). The page shows none of it.
3. **The judge column is the only split that means anything on Gaia2.** The
   scripted judge passes 52 of 98 rollouts; the soft judge passes 0 of 492.
   The page tags the minority judge per mark but never states either rate.

On review, Michael set the goal above any one of these: **a system that is easy
to read, well designed, and automatically tracks all results.** The first
draft of this spec embedded one campaign and relied on a script being re-run;
both are out. Of three tracking models offered -- index everything with
auto-refresh, embed everything in full, or a live local server -- he chose the
first, which keeps the no-server, single-file loading model that `DESIGN.md`
and `PRODUCT.md` require.

## Goals

1. **Every episode ever run is on the page**, with its verdict, judge, parse,
   configuration, stop facts and shaping signals -- 613 today -- without the
   page growing past what opens instantly from `file://`.
2. **No one re-embeds by hand.** The tools that produce results refresh the
   page themselves when they finish.
3. A reader can see **which parse graded each verdict**, with the default
   stated once and only departures tagged.
4. A reader can see **success split by judge** as a sentence, not a tile.
5. A reader can see **whether the world ended an episode**, and at what point
   of its horizon, in the runs table and in the episode's own view.
6. An evidence file's **summary** is visible above its rows.
7. **Easy to read across campaigns**: one campaign at a time by default, all at
   once on request.

## Non-goals

- **No live campaign monitor** for a run in flight. Separate follow-on.
- **No server, no build step, no network, no new loading model.** The
  embedded snapshot, drag-and-drop and the file picker remain the whole of it.
- **No new colours, tokens, tiles, cards, hero figures, or motion.** Every
  rule in `DESIGN.md` stands; the contrast validator is untouched.
- **No change to what the judge decides.** Display only; it reads fields that
  already exist on disk.

## Design

### 1. The snapshot: an index of everything, transcripts for the current campaign

`scripts/embed_logs.py` builds the snapshot in two parts.

**`index`** -- one compact record per episode under `output/rollouts/`, every
label, every campaign, in `started_at` order. Measured today: 613 records,
642 bytes each, 0.39 MB in total. Each record is exactly the set of fields the
runs view reads, plus what a stub detail view needs:

    kind ("gaia2-episode"), index_only (true), path, scenario_id, config,
    ability, label, judge, judge_parse, started_at, seconds, main_model,
    sub_model, delegations, specialist_turns, malformed, blocked,
    false_outages, answer (first 160 chars), verdict {success, rationale
    (first 1,200 chars)}, stop {time_passed, duration, env_state} from the last
    instrumented stop event or null, credit {partial_reward, coverage,
    fidelity, pivot, pivot_kind} or null

**`files`** -- as today: every `sweep/*.json`, every
`jobs/**/verifier/breakdown.json`, and the **full trajectories of one label**:
the current campaign, named by `--label` or defaulting to the label whose most
recent `started_at` is newest. For v6 that is 126 files and 5.5 MB. The
snapshot's top-level object gains `labels` (every label in the index) and
`full_label` (the one whose transcripts are embedded). Page size today:
about 7 MB, down from 8.9 MB.

The `MAX_BYTES` per-file guard stays for `files`; index records are never
near it. `--label` naming a label with no rollouts exits non-zero listing the
labels present. The module docstring's opening -- "reads the live repository
through a remembered browser directory handle" -- describes the retired File
System Access layer and is replaced with the actual loading model.

### 2. Loading the index: stubs that a real file replaces

`loadSnapshot` adds every `index` record through `addSession(name, path,
data)` before adding `files`. Each record already carries `kind:
"gaia2-episode"`, so `detect()` is untouched and `byKind("episode")` returns
stubs and full trajectories alike. `addSession` de-duplicates by `path` and
keeps the later entry, so a full trajectory embedded for the current label, or
a file dropped or picked later, **replaces its stub with no further logic**.
`sourceLine` becomes *"snapshot of 2026-08-31 14:10 · 613 episodes across 6
campaigns · transcripts for v6 · 54 evidence files"*.

Every consumer of episode sessions is accounted for: `runStats` and
`renderRuns` read only index fields; `renderEpisode` is the one place that
reads `events`, and §5 gives it a stub branch.

### 3. Readable across campaigns: the campaign picker

The runs view's existing `.filterline` gains a first control, a `<select>`
labelled *campaign*, listing every label in the index newest first plus
*"all campaigns"*. It defaults to `full_label`. The verdict grid, the signal
chips, the judge sentence and the runs table all compute from the selected
set. It is a filter in the filter line, not a header action: the header's two
actions are pinned by test and stay two.

With *"all campaigns"* selected, the grid's cells hold one mark per run as
today, and the existing rule -- a `.runlab` label beside a mark only when its
cell holds more than one run -- is what keeps that readable.

### 4. The parse stamp, and success by judge

A helper `parseLabel(d)` returns `d.judge_parse` when present and `"stock"`
when absent. The runs view computes `majorityParse` over the selected set the
same way it computes `majorityJudge` (most common; ties break on name) and
follows the same rule the judge already follows:

- The grid note states the majority once. When it is `"stock"`, the note adds:
  *"Soft-judge verdicts were read under the benchmark's stock parse, which
  recorded its checker's `[[true]]` as a failure; see
  `sweep/gaia2_v6_judge_parse.json`."* When it is `case-insensitive-v1`, that
  sentence is omitted and the parse is named instead.
- Only marks and rows whose parse differs from the majority carry a `.tag`
  with the parse label, beside the judge tag when both apply.
- The parse label is appended to each row's `data-text`, so the free-text
  search already filters on it; no new control.

Today, with v6 selected, every row is `"stock"`, the note says so, and nothing
is tagged. When a v7 campaign runs under the fix, selecting it names
`case-insensitive-v1`; selecting *"all campaigns"* makes the v6 rows the
tagged minority automatically.

The grid note gains one computed sentence after the default-judge sentence:
*"Scripted judge: 5 of 11 passed. Soft judge: 0 of 115 passed."* -- one
clause per judge present in the selected set, scripted first, omitting a
judge with zero runs. Prose in the existing `.note`; not a tile.

### 5. The stop row

**Runs table.** A new `ended` column between `issues` and `answer`:

- `answered` when `answer` is not the `ENV_STOP` sentinel
  `"(environment stopped)"`;
- `world stopped at 313/1000 s` when it is and `stop` is present
  (`Math.round` on both, integers); `world stopped at 313 s` when `duration`
  is null;
- `world stopped` when it is and `stop` is null (pre-`a59d9bb` runs);
- `--` when `answer` is null.

Rows whose answer is the sentinel carry `stopped` in `data-issues` beside any
existing `malformed` / `blocked` / `errors` keys.

**Signal chip.** `runStats` counts episodes whose answer is the sentinel;
`renderSignals` adds a `warn` chip *"N stopped by the world"* that sets
`issueFilter = "stopped"` exactly as the other chips do. Disjoint from the
three existing counts by construction -- it is an outcome, and
`countMalformed`, `countErrors` and `blocked` never read the answer. Appears
only when non-zero.

**Episode view.** The run bar's facts line gains `judge parse <b>…</b>` when
`judge_parse` is present and nothing when absent. Under the verdict panel,
when the answer is the sentinel, one line in the `.credit` component reads

> world stopped · **956** of **1000** simulated seconds used · STOPPED

with the environment's `reason` in the line's `title`; or *"world stopped ·
no clock recorded for this run"* when `stop` is null. Absent when the episode
answered.

**Stub branch.** When `s.data.index_only` is true, `renderEpisode` renders the
run bar, the verdict panel (from the index's truncated rationale, through
`parseRationale` as today), the shaping-signals line, the stop line, and then
-- in place of the transcript -- one `.abstract` block: *"This copy of the page
carries the transcript only for the v6 campaign. Open
`output/rollouts/<file>` with **open files**, or drop it here, and it replaces
this summary."* The path is the index record's `path`.

### 6. Evidence summary

When a sweep file's `data` carries a `summary` object, `renderSweeps` renders
it as a `.note` block above the table: one `key: value` line per top-level
key, object values as compact JSON on one line, truncated at 160 characters
with a `title` carrying the whole. Nothing file-specific.

### 7. Auto-refresh: the producers refresh the page

`scripts/embed_logs.py` exposes `refresh(label=None)` -- what `main()` calls
-- and prints one line naming the page size and the labels embedded. Three
producers call it at their end, after their own output is written and only on
a real run:

- `scripts/gaia2_campaign.py`, after the pool completes and the
  *"campaign complete"* line, with `label=args.label`. The `--dry-run` path
  returns before the pool and never refreshes.
- `scripts/gaia2_campaign_summary.py` and `scripts/gaia2_credit_probe.py`,
  after `dest.write_text`, with `label=args.label`.

Each passes its label so the page's transcripts follow the campaign just
produced. A refresh failure (for example a malformed rollout) is reported on
one line and does not fail the producer: the results are already on disk, and
the page is a view of them.

`README.md`'s Gaia2 section drops its instruction to run `scripts.embed_logs`
by hand and says the campaign, summary and credit commands refresh the page
themselves; the manual command stays documented for refreshing without a run.

### Edge cases

- **A picked or dropped file for an episode already embedded in full**: the
  later `addSession` wins, as today.
- **An index record and no matching file on disk** (a rollout deleted after
  the snapshot): the stub renders and its `.abstract` block names a path the
  picker will not find; the reader sees the record, not an error.
- **Two instrumented `stop` events in one trajectory**: the last wins, both in
  the index builder and in `renderEpisode`.
- **`--label` omitted with no rollouts on disk**: `index` and `labels` are
  empty, `full_label` is null, the runs view's existing empty state applies.
- **The campaign picker with one label in the index**: rendered anyway, with
  its one label and *"all campaigns"*; a control that behaves the same at
  every scale is easier to read than one that appears at a threshold.
- **`hasLabels` column in the runs table**: unchanged; the parse tag is on the
  verdict cell.

## Verification

Tests first, watched failing, in `forge/tests/test_viewer.py` and a new
`forge/tests/test_embed_logs.py`:

- `snapshot()` returns `index`, `files`, `labels`, `full_label`; every rollout
  on disk yields exactly one index record with the fields listed in §1 and no
  `events`; only `full_label`'s rollouts appear in `files`; every sweep and
  breakdown file appears in `files`; an unknown `--label` raises `SystemExit`;
  `refresh()` is importable and idempotent on an unchanged tree;
- `loadSnapshot` adds `index` records before `files` (source order), and the
  runs-view source contains `index_only`;
- the filter line contains a `campaign` select and the header still has
  exactly two actions;
- the grid block contains `parseLabel(` and `majorityParse`, still calls
  `badge(` directly, and its note names the sweep file when the majority is
  `"stock"`;
- the runs table header contains `<th>ended</th>`; `stopped` is set on
  `data-issues`; `countErrors` and `countMalformed` are unchanged;
- `renderSignals` emits a chip with key `stopped` and kind `warn`;
- `renderEpisode` has an `index_only` branch that renders `.abstract` and no
  `.transcript`, shows `judge parse` only when the field is present, and the
  `.credit` stop line only when the answer is the sentinel;
- `renderSweeps` renders a `summary` block when present and nothing when
  absent;
- each of the three producers calls `refresh(` after its output is written,
  and `gaia2_campaign`'s call is unreachable from `--dry-run`.

Then: full suite green; `ruff check forge scripts` clean; contrast validator
untouched and passing; `uv run python -m scripts.embed_logs` producing a page
under 8 MB whose `sourceLine` names 613 episodes and v6; the page opened from
`file://`, showing v6 by default with the stock-parse note and the two-judge
sentence, *"all campaigns"* showing every label, an `ended` cell, the stop
chip filtering, a v6 episode's stop line, a `full`-campaign stub with its
`.abstract` block, that stub replaced by picking its file, and the judge-parse
file's transitions above its rows.
