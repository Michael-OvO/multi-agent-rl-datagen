---
name: rl-datagen — Run dashboard
description: A dashboard you read at a glance — status carried by colour, icon, and word at once, over quiet tables in a single column.
colors:
  surface: "#fcfcfb"
  plane: "#f9f9f7"
  ink: "#0b0b0b"
  ink-2: "#52514e"
  muted: "#898781"
  grid: "#e1e0d9"
  axis: "#c3c2b7"
  hair: "rgba(11, 11, 11, 0.10)"
  wash: "rgba(11, 11, 11, 0.035)"
  pass: "#0ca30c"
  warn: "#fab219"
  fail: "#d03b3b"
  pass-ink: "#006300"
  warn-ink: "#8a5a00"
  fail-ink: "#b42318"
  pass-tint: "rgba(12, 163, 12, 0.10)"
  warn-tint: "rgba(250, 178, 25, 0.16)"
  fail-tint: "rgba(208, 59, 59, 0.10)"
  surface-dark: "#1a1a19"
  plane-dark: "#0d0d0d"
  ink-dark: "#ffffff"
  ink-2-dark: "#c3c2b7"
  muted-dark: "#898781"
  grid-dark: "#2c2c2a"
  axis-dark: "#383835"
  hair-dark: "rgba(255, 255, 255, 0.10)"
  wash-dark: "rgba(255, 255, 255, 0.05)"
  pass-dark: "#0ca30c"
  warn-dark: "#fab219"
  fail-dark: "#d03b3b"
  pass-ink-dark: "#3ecb4a"
  warn-ink-dark: "#fab219"
  fail-ink-dark: "#f2655c"
  pass-tint-dark: "rgba(12, 163, 12, 0.16)"
  warn-tint-dark: "rgba(250, 178, 25, 0.16)"
  fail-tint-dark: "rgba(208, 59, 59, 0.20)"
typography:
  title:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', Inter, Roboto, system-ui, sans-serif"
    fontSize: "22px"
    fontWeight: 650
    lineHeight: 1.2
    letterSpacing: "-0.02em"
  section:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', Inter, Roboto, system-ui, sans-serif"
    fontSize: "16px"
    fontWeight: 650
    letterSpacing: "-0.01em"
  panel-title:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', Inter, Roboto, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 650
    letterSpacing: "-0.01em"
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', Inter, Roboto, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.6
  table:
    fontSize: "13.5px"
    fontWeight: 400
  table-header:
    fontSize: "12px"
    fontWeight: 500
    color: "{colors.muted}"
  status:
    fontSize: "12px"
    fontWeight: 600
  label:
    fontSize: "11.5px"
    fontWeight: 600
  note:
    fontSize: "12px"
    color: "{colors.muted}"
  mono:
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
    fontSize: "11.5px"
rounded:
  pill: "999px"
  panel: "10px"
  block: "8px"
  control: "7px"
spacing:
  page-max-width: "1080px"
  page-padding: "40px 40px 120px"
  page-padding-narrow: "22px 16px 90px"
  section-gap: "30px"
  panel-gap: "28px"
  signal-gap: "9px"
  legend-gap: "14px"
  filter-gap: "18px"
  cell-padding: "7px 16px 7px 0"
  turn-padding: "10px 0"
  turn-gutter: "26px"
  speaker-column: "118px"
components:
  status-badge:
    backgroundColor: "{colors.pass-tint} | {colors.warn-tint} | {colors.fail-tint}"
    textColor: "{colors.pass-ink} | {colors.warn-ink} | {colors.fail-ink}"
    rounded: "{rounded.pill}"
    padding: "2px 9px"
    typography: "{typography.status}"
  tag:
    backgroundColor: "transparent"
    textColor: "{colors.ink-2}"
    border: "1px solid {colors.hair}"
    rounded: "{rounded.pill}"
    padding: "1px 7px"
  signal-chip:
    backgroundColor: "{colors.surface} | {colors.warn-tint} | {colors.fail-tint}"
    textColor: "{colors.ink-2} | {colors.warn-ink} | {colors.fail-ink}"
    rounded: "{rounded.pill}"
    padding: "4px 11px"
  table-panel:
    backgroundColor: "{colors.surface}"
    border: "1px solid {colors.hair}"
    rounded: "{rounded.panel}"
    shadow: "0 1px 2px rgba(11, 11, 11, 0.06)"
  runbar:
    backgroundColor: "{colors.plane}"
    borderBottom: "1px solid {colors.hair}"
    position: "sticky"
  verdict-panel:
    backgroundColor: "{colors.wash} | {colors.fail-tint}"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.panel}"
    padding: "13px 16px"
  transcript-turn:
    railColor: "{colors.grid}"
    dotColor: "{colors.axis} | {colors.pass} | {colors.fail}"
    pivotRule: "2px solid {colors.fail}"
  filter-input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    border: "1px solid {colors.hair}"
    rounded: "{rounded.control}"
    padding: "3px 9px"
---

# Design System: rl-datagen — Run dashboard

> Scope: this system governs the repo's single visual surface,
> `trajectory_viewer.html`. The rest of the repository is CLI and Python;
> nothing here applies to non-visual code.

## Overview

**North star: a dashboard you read at a glance.**

Open the file and the first screen answers, without a click: how many runs
there are, which passed, what went wrong, and which scenario is worst. Status
is legible before any prose is read, because every status is a colour *and* an
icon *and* a word. The tables underneath carry the detail, and any mark or row
opens the run behind it.

**The reversal, recorded honestly.** This surface used to be an academic
proceedings/evidence page: numbered captions above every table, superscript
footnote marks with notes below, a near-monochrome palette with a single
rationed red accent, a founding refusal of "cards, chips, badges, tiles,
lanes", and a draft line under the title. On **2026-07-28 the user overturned
that direction outright.** The stated reasons: it read as a costume rather
than a tool; the text was too dense to scan; and the basic facts about a run —
did it pass, what models ran it, where did it break — could not be found at a
glance. Three replacements were weighed: a run-card grid, a master–detail
split, and an overview page over tables. **The overview-over-tables option was
chosen** — it keeps the data density the tables already earned while putting
verdicts, failure signals, and models where the eye lands first.

Everything the old direction refused is now permitted where it earns its
place: coloured status badges, filter chips, tinted panels, soft radii. The
accent discipline, the numbered captions, the footnote marks, and the
no-chrome refusal are **retired** — they do not govern this file any more, and
nothing in this document should be read as reviving them.

One thing from the earlier redesign survives unchanged and must keep
surviving: **the loading model.** The page carries its own data. A JSON
snapshot sits in the `#embedded-logs` block -- an index of every episode ever
run, every task in the pool with its runs linked, every evidence file, and the
full transcripts of the current campaign -- so opening the file *is* the
workflow, and the producers refresh it when they finish. Files may also be
dropped on the page or chosen through the "open files" picker. The File
System Access folder connection was retired and must not come back — no
permission prompt stands in front of the data.

**Key characteristics**
- Status by three channels at once: colour, icon, word.
- One 1080px column; overview above, tables below, details behind a click.
- Quiet ground, coloured only where something is true about a run.
- Both themes first-class; a manual toggle that beats the OS in both directions.
- Everything keyboard-reachable under one focus treatment.
- One self-contained file: no build step, no network, no external asset.

## Colors

A warm-neutral ground with three status roles painted on it. Every token is
defined in all three theme scopes — `:root`, the
`@media (prefers-color-scheme: dark)` block on `:root:not([data-theme="light"])`,
and the `:root[data-theme="dark"]` override — so the toggle wins over the OS
setting in both directions and neither scope drifts from the other.

### Ground and ink

| token | light | dark | used for |
|---|---|---|---|
| `--surface` | `#fcfcfb` | `#1a1a19` | table panels, chips, inputs, the extracted call block |
| `--plane` | `#f9f9f7` | `#0d0d0d` | the page itself, and the sticky run bar's opaque backing |
| `--ink` | `#0b0b0b` | `#ffffff` | primary text, focus outlines, the active tab's underline |
| `--ink-2` | `#52514e` | `#c3c2b7` | supporting prose: ledes, run facts, tool output, table sub-cells |
| `--muted` | `#898781` | `#898781` | de-emphasized labels only — table headers, timestamps, paths, notes |
| `--grid` | `#e1e0d9` | `#2c2c2a` | the transcript rail, a quiet call's left rule, stage-direction dots |
| `--axis` | `#c3c2b7` | `#383835` | the default rail dot — an event with no status of its own |
| `--hair` | 10% ink | 10% ink | panel borders, link underlines at rest, row and header rules |
| `--wash` | 3.5% ink | 5% ink | the only fill: row hover, quoted blocks, the passing verdict panel |

### Status

Each status role ships as three values, and each has one job:

| role | mark | text (`-ink`) | fill (`-tint`) |
|---|---|---|---|
| pass | `#0ca30c` (both modes) | `#006300` light / `#3ecb4a` dark | 10% light / 16% dark |
| warn | `#fab219` (both modes) | `#8a5a00` light / `#fab219` dark | 16% both |
| fail | `#d03b3b` (both modes) | `#b42318` light / `#f2655c` dark | 10% light / 20% dark |

The **mark** colours dots, rails, and borders — non-text, so 3:1 is the bar.
The **`-ink`** colours are the only ones allowed under text, and clear 4.5:1
against *both* grounds of their own mode. The **`-tint`** colours fill badges
and panels and are never the sole carrier of anything.

The warn row is the exception to the first sentence. `--warn` and the
`.badge.warn` rule are defined so the status set is complete in all three
theme scopes, but nothing on the shipped page paints a bare warn mark: no rule
reads `var(--warn)` and nothing calls `badge("warn", …)`. Warning reaches the
reader as fill plus text instead — `--warn-tint` behind `--warn-ink` on the
signal chips, and `--warn-ink` alone on the `.warn-text` counts (blocked,
malformed, faulted, the pivot flag, the shipped-task failure count, the
runs table's `ended` cell). That is
deliberate: the light value is sub-3:1, so warning is never asked to carry
meaning as a mark on its own.

### Named rules

**Three channels.** A status is a colour **and** an icon **and** a word,
always all three. `badge(kind, label)` is the single builder and it emits all
three structurally — icon from `ICONS`, escaped label, `aria-hidden="true"` on
the glyph so a screen reader hears the word once. This makes the palette
survive colour-blindness, greyscale printing, and forced-colors mode. The rule
governs marks where **colour is the primary carrier**: badges, signal chips,
rail dots, the run bar's verdict, tags. It does not reach a figure whose own
label already names its quantity — there colour is emphasis on top of a word
that is always present. That distinction was ruled on 2026-07-28; do not add
an icon to a number to satisfy the rule.

**Light-mode `--warn` is a documented sub-3:1 exception — and the reason
warning is never painted as a bare mark.** `#fab219` measures 1.74:1 on the
light plane (1.79:1 on the surface), well under the 3:1 a mark normally owes.
The token is kept, at that exact value, because the dataviz reference palette
validated its colour-vision separation there and because the status set would
otherwise be incomplete; a test pins the hex so nobody quietly "fixes" it. But
the value is why nothing on the page uses it as a dot, rail, or border. Warning
reaches the screen as `--warn-tint` fill under `--warn-ink` text on the signal
chips, and as `--warn-ink` on `.warn-text` counts — both of which clear 4.5:1
and both of which always sit beside a word. `.badge.warn` is defined for the
same completeness reason and currently has no caller.

**`--muted` is for de-emphasized labels only.** It is 3.41:1 in light mode —
enough for a table header, a timestamp, a file path, or a note, and not enough
for prose anyone must read. Body prose is `--ink` or `--ink-2`.

**Contrast is computed, not eyeballed.** Node.js is not installed on this
machine, so the usual palette validator cannot run. `forge/tests/test_viewer.py`
carries the WCAG math instead: it parses the three theme scopes out of the
stylesheet, asserts every token exists in each, asserts the two dark scopes
agree, and checks each status colour against both grounds of its mode. A new
shade is not "documented" until that file passes with it pinned.

## Typography

One family throughout: the system sans stack
(`-apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Inter, Roboto,
system-ui, sans-serif`), antialiased. Monospace
(`ui-monospace, SFMono-Regular, Menlo, Consolas, monospace`) is confined to
model names, tool-call signatures, file paths, extracted calls, and code.

### Hierarchy

- **Page title** 22px / 650 / -0.02em — once, in the header.
- **Section heading** (`h2.sec`) 16px / 650, and the sticky run bar's `h3` at
  the same size so a detail view reads as a peer of a section.
- **Panel title** (`.panel-title`) 14px / 650, with a 12.5px `--ink-2` `.sub`
  clause that says what clicking does.
- **Body** 14px / 1.6; ledes clamp at 78ch, notes at 84ch, the empty state at
  66ch.
- **Table** 13.5px body, 12px / 500 `--muted` headers in sentence case.
- **Transcript** 13px matter, 11.5px / 600 speaker label with a 10.5px
  timestamp beneath it.
- **Status** 12px / 600 in badges and chips; `.tag` and `.runlab` 11px.
- **Mono** 11–11.5px everywhere it appears.

`font-variant-numeric: tabular-nums` is set once, on `body`. Every figure the
page shows now lives in a table column, a fact line, or a chip — the display-
size figures that would have been disfigured by fixed-width digits were
removed with the summary band, so a single global declaration is the honest
implementation of "aligned columns". If a display figure is ever added, it
needs proportional figures and its own override.

## Layout

A single centred column: `max-width: 1080px`, padding `40px 40px 120px`
(`22px 16px 90px` under 720px). Nothing is ever wider; nothing is a sidebar.

The **header** is the page title, two quiet actions ("open files", "theme"),
and a one-line source statement in `--muted` naming where the loaded data came
from. Under it, three text tabs on a hairline baseline — Runs, Shipped-task
runs, Evidence files — the active one bold with a 2px `--ink` underline.

The **Runs view**, in order:

1. `Runs` section heading.
2. The **failure-signal chips** — malformed protocol lines, blocked calls,
   faulted tool calls, worst scenario. Each is a button; clicking filters the
   table below. A chip that would read zero is not rendered at all.
3. The **verdict grid** — scenarios down, configurations across, a badge per
   run, with its legend above and its explanatory note below.
4. The **all-runs table** — filter line, then every run newest first.

**Shipped-task runs** and **Evidence files** follow the same shape: heading,
lede, panel title, filter line, table.

**Detail views** (a run's transcript, a shipped-task ledger, a raw file) open
in place from a mark or a row. They begin with a back line ("← back to the
tables (esc)"), then the sticky run bar, then the verdict panel, then the
transcript. Scroll position is saved on the way in and restored on the way
back; Escape closes.

Tables sit in a `.tabwrap` panel that scrolls horizontally only if it must;
cells are single-line and ellipsize at 380px, except in `.wrap` tables, which
trade taller rows for no horizontal scrolling at all. Numeric columns are
right-aligned.

## Components

**Status badge** (`badge(kind, label)`) — a pill: tint fill, `-ink` text, icon
then word, 999px radius. `verdictBadge(ok, judge)` wraps it for run headers and
appends a judge tag when one is warranted. This is the only way a status gets
painted; there is no bare coloured dot with no word beside it outside the
legend and the transcript rail.

**Tag** (`.tag`) — a hairline outline pill in `--ink-2`, no fill, no colour. It
qualifies the thing before it: which judge scored this run, which re-run this
mark is. Being colourless is the point — a tag is a footnote, not a status.

**Signal chip** (`.signal`) — a button pill. Neutral chips sit on `--surface`
with a hairline border; `warn` and `fail` chips take their tint and `-ink` and
drop the border. Active chips carry the shared focus outline (`.on`). Clicking
a chip filters the runs table; clicking the "worst scenario" chip seeds the
search box with that scenario instead.

**Panel title + legend** — a 14px/650 line naming the table and a 12.5px `.sub`
saying what a click does, then, for the verdict grid, a legend of dot + word
for pass, fail, and "— not run".

**Tables** (`table.tab` inside `.tabwrap`) — a `--surface` panel with a
hairline border, 10px radius, and one 1px shadow. Header row 12px/500 in
`--muted` under a hairline; body rows separated by `--wash`; hover fills a row
with `--wash`; `tr.click` is focusable and Enter/Space-actionable.

**Run bar** (`.runbar`) — sticky at the top of every detail view, on an opaque
`--plane` ground with a hairline under it. It carries the verdict badge, the
scenario, the configuration, and a facts line: ability, models, delegations,
specialist turns, wall seconds, judge, plus malformed and blocked counts in
`--warn-ink` when they are non-zero. Scroll 200 turns down and you still know
what you are reading.

**Verdict panel** (`.verdict-panel`) — the judge's finding, read before the
transcript. `--wash` when the run passed, `--fail-tint` when it failed. Its
signature move is the **extracted gold write**: `parseRationale()` pulls the
tool name and arguments the judge expected out of the wall of text and sets
them in a monospace block on `--surface`, folding wrapped values into the
argument above them; the log of matching attempts goes behind a disclosure. A
rationale of the literal string `"None"` is treated as absent.

**Shaping signals** (`.credit`) — a single line beside the verdict, never
instead of it: partial reward, coverage, fidelity of gold writes, and the
pivot. This predates the redesign (commit `d844695`) and is restyled, never
dropped.

**Transcript turn** (`.turn`) — a 118px speaker column and a fluid matter
column with a 26px gutter (84px/20px under 720px). A 2px `--grid` rail runs
through the gutter, and each turn puts a dot on it coloured by `turnStatus(e)`:
`--pass` for a completed run, `--fail` for a surrender, stop, or faulted call,
`--grid` for stage directions (waits, notifications), `--axis` otherwise. Tool
calls collapse under a disclosure and open by default when one of them faulted;
a faulted call's left rule turns `--fail` and its status is named in words.
**The pivot** — the first faulting event, frozen prefix above it and trainable
suffix below — is a boundary, not another event, so it gets a 2px `--fail` rule
across the whole turn plus a `.pivotflag` line, rather than a fourth dot colour.

**Filter line** (`.filterline`) — a search input and selects on `--surface` with
a hairline border and 7px radius, the running count flush right in `--muted`
("all 64 runs" until something is filtered out, then "12 of 64 runs"). Filters
compose: text, verdict, ability,
judge, and whichever signal chip is active.

**Empty state** (`.abstract`) — when the snapshot is empty, one 66ch block that
names the cause and the fix (`uv run python -m scripts.embed_logs`) and offers
drag-and-drop. Each view has its own version for "loaded, but nothing of this
kind". The same class carries a second role: an index stub's episode view
renders an `.abstract` block reading *"Transcript not in this copy"*, naming
the campaign the page carries in full and inviting the reader to open or
drop the file it names, which replaces the stub.

**Motion** — one authored moment: `#content` settles on every navigation
(`settle 0.22s cubic-bezier(0.16, 1, 0.3, 1)`, a fade from `translateY(4px)`),
restarted by reflow per render and suppressed under
`prefers-reduced-motion: reduce`. There is no other animation or transition.

### Named rules

**Annotate the exception, not the rule.** A per-cell annotation that lands on
nearly every cell is not information — it is texture. The verdict grid used to
tag 264 of its 314 marks with the judge that scored them. Now the majority
judge is named once, in the grid's note, and only the marks that departed from
it are tagged — about 25. The same rule governs run labels: a label appears
beside a mark only when its cell holds more than one run, because a label that
distinguishes nothing is noise.

**Counts mean one thing.** Two counters that a reader takes to be disjoint must
be disjoint. `countErrors()` explicitly skips `malformed`, because
`countMalformed()` already reports those; without the exclusion, one bad
protocol line would be counted by the "malformed" chip and the "faulted" chip
both, and the two numbers would silently overlap.

**No tiles, and no hero figure.** A boxed summary band of big numbers — total
runs, success rate, failures, models — was built on 2026-07-28 and removed the
same day at the user's instruction: it restated numbers the tables already
carry, and it was chrome. The failure-signal chips survived that cut because
they are light and each one *does* something when clicked. Do not reintroduce
tiles, cards, or a display-size figure on any view.

**One focus treatment.** Every focusable thing — links, `.xref` spans, buttons,
inputs, selects, disclosure summaries, clickable rows, sortable headers, the
file-picker label — shares `outline: 2px solid var(--ink); outline-offset: 2px`.
Anything new that can be clicked must also be reachable by Tab and actionable
by Enter or Space.

## Do's and Don'ts

### Do

- **Do** paint every status through `badge(kind, label)` so it ships colour,
  icon, and word together.
- **Do** define any new token in all three theme scopes — `:root`, the
  `prefers-color-scheme: dark` media query, and `:root[data-theme="dark"]` —
  and keep the two dark scopes identical.
- **Do** re-run `forge/tests/test_viewer.py` after touching any colour; it is
  the contrast validator on this machine.
- **Do** keep annotations for departures from the stated default, and state the
  default once in the panel's note.
- **Do** keep counters disjoint when they are presented as disjoint.
- **Do** keep the file self-contained: no external stylesheet, script, font, or
  image; no network request; no build step. It must work from `file://`.
- **Do** keep new interactive elements focusable, Enter/Space-actionable, and
  covered by the shared focus outline; keep Escape closing a detail view.
- **Do** use `--muted` for labels, timestamps, paths, and notes only.

### Don't

- **Don't** let colour carry a status alone — no bare coloured dot, cell, or
  word standing in for a verdict outside the legend and the transcript rail.
- **Don't** invent a shade outside the documented palette without adding it to
  the token tests and re-running the contrast math; in particular, don't
  "correct" `--warn`'s light value, which is a deliberate, mitigated exception.
- **Don't** reintroduce stat tiles, cards, or a display-size hero figure; they
  were built and removed by decision, not by oversight.
- **Don't** tag every row or cell with the same qualifier — name the majority
  once and tag only what differs.
- **Don't** set prose in `--muted`, or set labels, numbers, or verdicts in
  monospace; monospace is for model names, call signatures, paths, and code.
- **Don't** add motion beyond the single settle, or bypass its reduced-motion
  guard.
- **Don't** reintroduce a permission-gated data source. The embedded snapshot,
  drag-and-drop, and the file picker are the entire loading model.
- **Don't** hand-edit the `#embedded-logs` block or its script tags;
  `scripts/embed_logs.py` rewrites it by regex and breaks if the tags change.
