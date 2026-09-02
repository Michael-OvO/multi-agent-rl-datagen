# Bring the trajectory viewer current: the parse, the stop, the judge

Date: 2026-08-31
Status: approved design, pending spec review

## Context

`trajectory_viewer.html` is the repository's single visual surface, and its
whole loading model is a JSON snapshot embedded in the page (`#embedded-logs`),
plus drag-and-drop and a file picker. That snapshot was last generated on
2026-07-28 16:20. It carries 239 files: the `full` campaign's 173 episodes, 20
probe episodes, and seven Gaia2 evidence files -- `gaia2_full_campaign.json`,
`gaia2_credit.json`, the cells and admission files. Nothing from v3, v4, v5 or
v6 is in it. No embedded episode carries a `judge_parse` stamp or an
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

The page therefore tells a reader that Gaia2 fails everything, without the one
fact that explains it. This design makes the page tell the truth about Gaia2
for the first time, inside the constraints `DESIGN.md` already governs.

## Goals

1. The snapshot carries the **current campaign** and every evidence file, and
   the page opens fast enough to be the workflow.
2. A reader can see, without opening a run, **which parse graded each verdict**,
   with the default stated once and only departures tagged.
3. A reader can see **success split by judge** as a sentence, not a tile.
4. A reader can see **whether the world ended an episode**, and at what point
   of its horizon, both in the runs table and in the episode's own view.
5. An evidence file's **summary** (the judge-parse file's transitions, a credit
   file's per-cell means) is visible above its rows instead of only inside its
   JSON.

## Non-goals

- **No live campaign monitor.** A progress view for a run in flight is a
  separate follow-on that reads the same rollouts directory.
- **No new colours, tokens, tiles, cards, hero figures, or motion.** Every rule
  in `DESIGN.md` stands; the contrast validator in `forge/tests/test_viewer.py`
  is not touched.
- **No new loading model.** The embedded snapshot, drag-and-drop and the file
  picker remain the whole of it. Nothing permission-gated returns.
- **No change to what the judge decides.** This is a display change; it reads
  fields that already exist on disk.

## Design

### 1. Embed policy (`scripts/embed_logs.py`)

Re-embedding everything under `output/rollouts/` would put 613 files and
30.5 MB into a page that is 8.9 MB today. The snapshot instead carries:

- every `sweep/*.json` (32 files, 0.8 MB) and every
  `jobs/**/verifier/breakdown.json` (22 files, 27 KB), as today;
- rollouts for **one label only**: the label named by a new `--label` flag,
  defaulting to the newest label present (newest by the `started_at` of the
  most recent file carrying it). For v6 that is 126 files and 5.5 MB, giving a
  page near 7 MB -- smaller than today's.

The `MAX_BYTES` per-file guard (2,000,000) stays; no current rollout exceeds
it (largest: 994,408 bytes, a v4 file). The snapshot's top-level object gains
`labels`: the list of labels it carries (one entry under this policy), so the
page can say what it holds. Older campaigns stay reachable by drag-and-drop or
the file picker.

The module docstring's opening -- "The viewer normally reads the live
repository through a remembered browser directory handle" -- describes the
retired File System Access layer and is replaced with the actual loading
model. `README.md`'s Gaia2 section already tells readers to run
`scripts.embed_logs`; its sentence gains the `--label` flag.

### 2. The parse stamp

`judge_parse` is read wherever `judge` is read. A helper `parseLabel(d)`
returns `d.judge_parse` when present and `"stock"` when absent. The runs
view computes a `majorityParse` the same way it computes `majorityJudge` (most
common; ties break on name) and follows the same rule:

- The grid note states the majority once. When it is `"stock"`, the note
  adds: *"Soft-judge verdicts were read under the benchmark's stock parse,
  which recorded its checker's `[[true]]` as a failure; see
  `sweep/gaia2_v6_judge_parse.json`."* When it is `case-insensitive-v1`, the
  note states that instead and the sentence about the defect is omitted.
- Only marks and rows whose parse differs from the majority carry a `.tag`
  with the parse label, beside the judge tag when both apply.
- The runs table's judge `<select>` gains no new control; the parse is
  filterable through the existing free-text search, which already indexes
  each row's `data-text` (the parse label is appended to that JSON).

This means that today, with an all-v6 snapshot, every row is `"stock"`, the
note says so plainly, and nothing is tagged. When a v7 campaign runs under the
fix and is embedded, `case-insensitive-v1` becomes the majority and the v6
rows, if also loaded, become the tagged minority -- with no further change.

### 3. Success by judge

The grid note gains one computed sentence after the default-judge sentence:
*"Soft judge: 0 of 115 passed. Scripted judge: 5 of 11."* -- one clause per
judge present, in the order scripted then soft, omitting any judge with zero
runs. It is prose in the existing `.note`, computed from the loaded episodes.
It is not a tile, a card, or a display-size figure, and adds no element.

### 4. The stop row

**Runs table.** A new `ended` column between `issues` and `answer`:

- `answered` when the episode's `answer` is not the `ENV_STOP` sentinel
  `"(environment stopped)"`;
- `world stopped at 313/1000 s` when it is, reading `time_passed` and
  `duration` from the last `stop` event that carries `time_passed`
  (`Math.round` on both, shown as integers);
- `world stopped` alone when the answer is the sentinel but no instrumented
  stop row exists (pre-`a59d9bb` trajectories);
- `--` when there are no events at all.

Rows whose answer is the sentinel carry `stopped` in `data-issues`, alongside
any existing `malformed` / `blocked` / `errors` keys.

**Signal chip.** `runStats` counts episodes whose answer is the sentinel;
`renderSignals` adds a `warn` chip *"N stopped by the world"* that sets
`issueFilter = "stopped"` exactly as the other chips do. The count is disjoint
from the three existing counts by construction: it is an outcome, and
`countMalformed`, `countErrors` and `blocked` do not read the answer. Like the
other chips it appears only when non-zero.

**Episode view.** The run bar's facts line gains `judge parse <b>…</b>` when
`judge_parse` is present and nothing when it is absent -- the run bar names
what a run carries, not what it lacks. Under the verdict panel, when the
answer is the sentinel and an instrumented stop row exists, one line in the
`.credit` component reads:

> world stopped · **956** of **1000** simulated seconds used · STOPPED

with `reason` behind a `title` attribute on the line, since it is a sentence
of the environment's own and belongs to the transcript's stop event, which
already renders it. When the answer is the sentinel and no instrumented row
exists, the line reads *"world stopped · no clock recorded for this run"*.
When the episode answered, the line is absent.

### 5. Evidence summary

`renderSweeps` already reads `s.data.note` and `s.data.rows`. When `s.data`
also carries a `summary` object, a `.note` block above the table renders it as
`key: value` lines, one per top-level key, with object values shown as compact
JSON on one line and truncated at 160 characters with a `title` carrying the
whole. Nothing is file-specific: the judge-parse file's `transitions`, a credit
file's per-cell means, and any future summary all render the same way.

### Edge cases

- **Mixed-parse snapshot** (v6 dropped onto a v7 page): handled by the
  majority rule in §2; no special case.
- **A label with zero files** passed to `--label`: the script exits non-zero
  naming the labels present. It does not silently embed nothing.
- **`--label` omitted with no rollouts on disk**: the snapshot carries evidence
  files only and `labels` is empty; the runs view's existing empty state
  applies.
- **A `stop` event without `duration`** (a world that declares none, per
  `AreWorld.clock_facts`): the table cell reads `world stopped at 313 s`,
  omitting the horizon rather than printing `null`.
- **Two `stop` events in one trajectory** (observed in pre-fix runs): the last
  one carrying `time_passed` wins.
- **The runs table's `hasLabels` column**: unchanged; the parse tag is on the
  verdict cell, not the run-label column.

## Verification

Tests first, watched failing, in `forge/tests/test_viewer.py` and a new
`forge/tests/test_embed_logs.py`:

- the grid note branches on `majorityParse` and names the sweep file when the
  majority is `"stock"`;
- `parseLabel(` and `majorityParse` appear in the grid-building block, and the
  block still calls `badge(` directly (the existing anchor test keeps passing);
- the runs table header contains `<th>ended</th>`; the `stopped` key is set on
  `data-issues`; `countErrors` and `countMalformed` are unchanged;
- `renderSignals` emits a chip whose key is `stopped` and whose kind is `warn`;
- `renderEpisode` renders `judge parse` in the facts line only when the field
  is present, and the `.credit` stop line only when the answer is the sentinel;
- `renderSweeps` renders a `summary` block when present and nothing when absent;
- `embed_logs.snapshot(label=...)` includes only that label's rollouts, includes
  every sweep and breakdown file, records `labels`, and refuses an unknown
  label.

Then, in order: the full suite green; `ruff check forge scripts` clean; the
contrast validator untouched and passing; `uv run python -m scripts.embed_logs`
producing a page under 8 MB; the page opened from `file://` in a browser,
showing v6 with the stock-parse note, the two-judge sentence, `ended` values,
the stop chip filtering, one episode's stop line, and the judge-parse file's
transitions above its rows.
