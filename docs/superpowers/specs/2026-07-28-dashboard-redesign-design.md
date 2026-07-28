# Trajectory viewer redesign: evidence page → run dashboard

Date: 2026-07-28
Status: approved direction, pending spec review

## Context

`trajectory_viewer.html` is the repository's single visual surface. It currently
imitates an academic paper's evidence section: captions like "Table 1: …",
dagger footnotes, a "draft line", dense prose, and a near-monochrome palette
with one red accent. That direction (documented in `DESIGN.md`) explicitly
refused cards, stat tiles, badges, and color.

On 2026-07-28 Michael rejected that direction: it reads as a "fake design
vibe", the text is too dense, and the basic key information about runs is not
findable at a glance. The decision, made explicitly in this session: **drop the
academic-paper conceit and make it a real dashboard.** This overturns the
founding "no chrome" refusal in `DESIGN.md`; that document will be rewritten to
match the new direction.

## Goals (from the clarifying questions)

Visible at a glance, without scrolling or reading table rows:

1. **Totals and success rate** — how many episodes ran, how many succeeded,
   how many failed.
2. **Failure signals** — where failures and protocol issues concentrate:
   malformed protocol lines, blocked tool calls, the worst-performing scenario.
3. **Models** — which language models each run used (main agent model and
   sub-agent model).
4. **Trajectory clearness** — when a run is opened, its transcript (the
   turn-by-turn record of user messages, agent actions, and tool calls) must be
   far easier to follow than today. Clarified meaning: a readable transcript
   view, not a per-run cleanliness score.

Chosen shape (of three options presented): **"Overview + tables"** — a
glanceable overview band on top, the existing verdict grid and runs table
restyled below it, and a rebuilt transcript view. Rejected alternatives: a
card-grid of runs (cards scan worse than tables past ~50 runs) and a
master-detail split view (biggest rebuild, cramped under ~1200px).

## Non-goals

- No change to how data gets into the page. The embedded JSON snapshot
  (refreshed by `uv run python -m scripts.embed_logs`), drag-and-drop, and the
  "open files" picker remain the whole loading model.
- No new data pipeline fields. The dashboard renders what the snapshot already
  carries (`main_model`, `sub_model`, `verdict`, `events`, counters).
- No dedicated overview band for the Shipped-task runs or Evidence files tabs —
  they get the same visual restyling and a one-line summary only.

## Design

### Page structure (unchanged skeleton)

One self-contained HTML file, no external assets. Three tabs — **Runs**
(landing), **Shipped-task runs**, **Evidence files**. Light and dark themes,
both first-class, with the existing toggle and `prefers-color-scheme` default.
Full keyboard reachability and the Escape/back scroll-restoration behavior are
preserved.

### Runs overview band (new)

- **Stat row, four tiles** (stat-tile contract: sentence-case label, semibold
  proportional-figure value):
  - *Episodes* — count of judged episodes.
  - *Success rate* — the leading number of the page (largest type).
  - *Failures* — count; rendered in the critical status color only when > 0.
  - *Models* — the model names in use (e.g. `gpt-5.6-sol`), split main/sub
    when they differ; multiple models across runs are listed.
- **Failure-signals line** beneath the tiles: malformed protocol lines,
  blocked calls, and the worst scenario (lowest pass rate), each as
  icon + colored text label. Clicking a signal applies the matching filter to
  the all-runs table below.

### Verdict grid and all-runs table (restyled)

- **Verdict grid** (scenario × configuration) keeps its matrix shape; marks
  become color-coded ✓ (status green) / ✗ (status red); soft-judged runs carry
  a small "soft judge" text tag instead of the dagger footnote. A one-line
  legend above the grid replaces the caption prose. Marks still open the run's
  transcript.
- **All-runs table** column order: verdict badge (colored pill, icon + word),
  when, scenario, configuration, ability, models, issues, answer, duration.
  Existing filter row stays (free-text search, verdict, ability, judge).
  Newest first. Rows click through to the transcript.
- Shipped-task runs (Table "verifier results") and Evidence files (sweep
  tables) adopt the same table styling and colored verdict badges.

### Transcript view (rebuilt)

- **Sticky run header**: verdict badge, scenario, configuration, ability,
  main/sub models, duration, judge — pinned while scrolling.
- **Verdict panel** directly below the header: the judge's rationale in a
  highlighted panel (red-tinted on failure), with the missing or mismatched
  gold write extracted and shown clearly rather than as raw dump text.
- **Conversation timeline**, typed per event:
  - User messages: labeled message blocks.
  - Agent turns: plain text blocks.
  - Tool calls: compact one-line rows — tool name in monospace, colored
    status (ok / rejected / malformed). Arguments and outputs collapsed by
    default; **failed calls come pre-expanded and highlighted.**
  - Delegations: indented beneath the spawning turn.
  - Waits, notifications, environment stops: muted.
- **Timeline rail**: a thin left rail with colored dots marking event status,
  for scanning where in the run things went wrong.

### Color system

Adopt the dataviz reference palette (see the dataviz skill,
`references/palette.md`) in place of the paper/single-red system:

- Surfaces: light `#fcfcfb` on page plane `#f9f9f7`; dark `#1a1a19` on
  `#0d0d0d`. Inks: primary/secondary/muted neutral tints per the reference.
- **Status palette (fixed):** good `#0ca30c` (pass), critical `#d03b3b`
  (fail), warning `#fab219` (malformed/blocked/soft-judge caveats).
- Status colors never carry meaning alone — always icon + text label (warning
  and serious are deliberately below 3:1 contrast on light surfaces).
- Text stays in neutral ink; only verdict/status words themselves take status
  color.
- Both themes define every token; the dark values are selected steps, not an
  automatic flip.

`DESIGN.md` is rewritten to document this system and records that the previous
direction's refusals were overturned by Michael's decision of 2026-07-28.

### Edge cases

- Empty snapshot → the existing friendly empty state, restyled.
- Missing fields (no model, no timestamp, no counters) → "—", never blank or
  `undefined`.
- Large snapshots → keep the chunked row rendering (`batchAppend`).
- Reduced motion → any transition honors `prefers-reduced-motion`.

## Verification

- Rebuild, open with the real embedded snapshot, in light and dark themes.
- Screenshot review for label collisions, overflow, and contrast.
- The status palette is taken as-validated from the dataviz reference; any
  *new* color roles introduced during implementation must pass
  `scripts/validate_palette.js` from the dataviz skill.
- Keyboard pass: tabs, grid marks, table rows, filters, collapsed tool calls
  all reachable and Enter/Space-actionable.
