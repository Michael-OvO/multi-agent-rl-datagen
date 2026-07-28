---
name: rl-datagen — Trajectory evidence viewer
description: The repo's evidence section in a modern rendition — hairline tables and one signal red, not a dashboard.
colors:
  paper: "#ffffff"
  ink: "#16181d"
  ink-secondary: "#4d5158"
  faint: "#676c73"
  rule: "rgba(22, 24, 29, 0.55)"
  hairline: "rgba(22, 24, 29, 0.14)"
  wash: "rgba(22, 24, 29, 0.035)"
  signal-red: "#b42318"
  paper-dark: "#101114"
  ink-dark: "#e8eaed"
  ink-secondary-dark: "#aab0b7"
  faint-dark: "#868c94"
  rule-dark: "rgba(232, 234, 237, 0.5)"
  hairline-dark: "rgba(232, 234, 237, 0.14)"
  wash-dark: "rgba(232, 234, 237, 0.05)"
  signal-red-dark: "#f2655c"
typography:
  display:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', Inter, Roboto, system-ui, sans-serif"
    fontSize: "21px"
    fontWeight: 650
    lineHeight: 1.2
    letterSpacing: "-0.015em"
  headline:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', Inter, Roboto, system-ui, sans-serif"
    fontSize: "16px"
    fontWeight: 650
    letterSpacing: "-0.01em"
  title:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', Inter, Roboto, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 650
    letterSpacing: "-0.01em"
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', Inter, Roboto, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', Inter, Roboto, system-ui, sans-serif"
    fontSize: "11.5px"
    fontWeight: 550
  mono:
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
    fontSize: "11.5px"
rounded:
  none: "0"
spacing:
  cell-gap: "16px"
  filter-gap: "18px"
  page-inline: "40px"
  page-top: "40px"
  section-gap: "30px"
components:
  table-evidence:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
  table-header:
    backgroundColor: "transparent"
    textColor: "{colors.faint}"
    typography: "{typography.label}"
  filter-input:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "1px 2px"
  xref-link:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
  verdict-failure:
    backgroundColor: "transparent"
    textColor: "{colors.signal-red}"
---

# Design System: rl-datagen — Trajectory evidence viewer

> Scope: this system governs the repo's single visual surface, `trajectory_viewer.html`.
> The rest of the repository is CLI and Python; nothing here applies to non-visual code.

## Overview

**Creative North Star: "The Evidence Section, Modern Rendition"**

This surface presents run trajectories the way a report presents results:
numbered tables with captions above them, daggers and table notes for
qualifications, a contents line of three sections, and file citations
(`.path` lines) under every claim. The reader reads Table 1's verdict grid,
follows a mark into a transcript, and trusts it because it cites its files.
The observability-console arrangement — cards, chips, stat tiles, colored
lanes — is refused entirely; this is a confirmed anti-reference, not a
default.

The material is white ground and cool ink, set in the system's modern sans.
Monospace is confined to code, tool-call signatures, and file paths. There
is exactly one accent, signal red, and it is spent only on failure and
fault. Structure comes from hairline rules and softly framed table panels
(10px radius, one whisper of shadow) — never from cards or chrome. Motion
is a single authored moment: each navigation settles into place.

**Provenance.** The concept-seed scripts could not run on the build machine
(no Node.js), so no seed key exists; the four-direction hand was dealt by
hand, disclosed, and the user chose the proceedings/evidence direction
explicitly (rank 1 of 7; over telemetry strip-chart, terminal ledger, and
the category standard). On 2026-07-28 the user redirected the rendition
("modern text, modern feel, no folder-connect step"): the evidence-page
structure, accent discipline, and no-chrome refusal carried over unchanged;
the bookish serif, small caps, italic headers, spelled-out numbers, and the
File System Access folder connection were retired. The page's sole data
source is now its embedded snapshot (plus drag-and-drop / open-files).

**Key Characteristics:**
- Neutral ink-on-white with a single failure accent, both themes first-class
- Hairline table grammar: 1px rules top, bottom, and under the header; nothing vertical
- Captions above tables ("Table N: …"), dagger + note for qualification
- One modern sans for everything; monospace confined to code, calls, and paths
- Soft-edged panels over a flat page; one 0.22 s settle motion
- Everything keyboard-reachable with one shared focus outline
- Zero-click data: the snapshot is embedded in the file itself

## Colors

A near-monochrome palette of cool ink tints on white, with one rationed accent.

### Primary
- **Signal Red** (`#b42318` light / `#f2655c` dark): marks ✗ failure verdicts,
  failing speakers, malformed and faulted calls, and `.bad` text. It appears
  nowhere else — never on links, headings, buttons, or emphasis.

### Neutral
- **Paper** (`#ffffff` light / `#101114` dark): the page. The only background.
- **Ink** (`#16181d` light / `#e8eaed` dark): primary text, focus outlines,
  active-tab underline, selection (inverted).
- **Secondary Ink** (`#4d5158` light / `#aab0b7` dark): supporting prose —
  draft line, colophon, ledes, run metadata, reports, tool output.
- **Faint Ink** (`#676c73` light / `#868c94` dark): the quietest legible tint —
  table headers, speaker labels, timestamps, `.path` citations, table notes.
  Held at ≥4.5:1 on its ground; citations must stay legible.
- **Rule** (55% ink light / 50% dark): the table's top and bottom rules.
- **Hairline** (14% ink): link underlines at rest, form-blank underlines, the
  header-row underline, nav baseline, transcript top rule, left rules on
  quoted `pre` blocks and rationale asides.
- **Wash** (3.5–5% ink): the only fill — row hover and turn separators.

### Named Rules
**The Signal Red Rule.** Red is spent only on failure and fault. If a thing
is not wrong, it is ink.

**The Hairline Rule.** A table's structure is horizontal and 1px: the
panel's hairline frame, a hairline under the header row, wash hairlines
between body rows. No vertical rules, no zebra striping.

Both themes are first-class: dark mode follows `prefers-color-scheme` and can
be overridden via `data-theme`; every token has a dark counterpart.

## Typography

**Everything:** the system sans stack (`-apple-system … system-ui, sans-serif`),
antialiased, with `font-variant-numeric: tabular-nums` global so table columns
align. **Mono:** `ui-monospace` stack, only where the Confined Monospace Rule
allows.

### Hierarchy
- **Display** (650, 21px, -0.015em): the page title. Once per page.
- **Headline** (650, 16px, -0.01em): section headings (`h2.sec`).
- **Title** (650, 15px, -0.01em): subsection headings (`h3.subsec`).
- **Body** (400, 14px/1.6): prose; ledes and run metadata clamp to 78–84ch.
  Table cells 13.5px; transcript text 13px.
- **Label** (550, 11.5px): table headers (faint), margin speaker labels
  (right-aligned, 132px column; 96px under 720px) with a 10.5px timestamp
  beneath.
- **Caption/Note** (13px caption with a 600-weight "Table N" lead / 12px note).
- **Mono** (11–12px): call signatures, `pre` output, `code`, `.path` citations.

### Named Rules
**The Confined Monospace Rule.** Monospace appears only in code, tool-call
signatures, and file paths. Prose, labels, numbers, and verdicts are sans.

**The Bold-Figure Rule.** Key counts in prose are digits emphasized with
weight (`<b>8</b> judged episodes`), never color, never spelled out.

## Layout

A single centered column, `max-width: 1080px`, padded 40px 40px 120px (22px
16px 90px under 720px). The first viewport is the title block (title, muted
data-provenance draft line, quiet text colophon: "open files · theme"), the
contents nav (three text tabs on a hairline baseline, active tab bold with a
2px ink underline), a summary sentence with bold figures, and Table 1 with
its caption and note.

Prose measures clamp at 66–84ch by role. Sections open with 30px top margin.
Tables are full-width inside a horizontally scrollable wrapper; cells pad
6–8px vertically and 16px to the right, numeric columns right-aligned.
Transcripts are a two-column grid (132px speaker margin / fluid text, 20px
gutter). Long values ellipsize at 380px in cells; `pre` blocks scroll within
capped heights.

## Elevation & Depth

Nearly flat: exactly one soft shadow (`0 1px 2px` at 5% ink light / 30%
black dark) on table panels, nothing else. Depth is typographic hierarchy,
the panel frames, and wash fills.

**The No-Chrome Rule.** Nothing on this page is a tile, card, chip, badge,
or lane. If information needs grouping, it gets a rule or a caption, not a
box.

## Shapes

Softened 2026-07-28 at the user's direction ("no hard, sharp edges"): tables
sit in framed panels (`--panel` ground, 1px hairline border, 10px radius,
one soft shadow), inputs and colophon actions are soft filled controls (7px
radius, hairline border), and quotations (`pre`, rationale) are wash-filled
blocks with 8px radius. Text links keep their hairline underlines. Radius is
spent on containers and controls only — never on marks, verdicts, or text.

## Components

### Tables (the primary component)
- **Caption:** above the table, 13px, "**Table N:** description".
  Qualifications get a superscript dagger (†) in the cell and a `.tnote`
  below ("† judged by Gaia2's official soft judge").
- **Header row:** 11.5px, weight 500, faint ink, sentence case — data labels,
  not shouting UI headers.
- **Verdicts:** typeset, not badged — `✓ success` in ink, `✗ failure` in
  signal red, dagger appended when soft-judged.
- **Rows:** clickable rows (`tr.click`) and sortable heads (`th.sortable`)
  get pointer + wash hover, are focusable, and are Enter/Space-actionable.

### Filter line
- Soft filled inputs/selects: `--panel` ground, hairline border, 7px radius,
  3px 9px padding, 12.5px, labels in secondary ink; border darkens on focus.
  The running count sits flush right in faint ink.

### Links / cross-references
- Inherit ink, never a color change; hairline underline darkening to ink on
  hover. `.xref` spans behave identically to anchors, keyboard included.
- Every focusable element shares one treatment: `outline: 2px solid
  var(--ink); outline-offset: 2px`.

### Transcript turns (signature component)
- Two-column grid: right-aligned 11.5px/550 speaker label (10.5px timestamp
  beneath) in the margin; pre-wrapped 13px text in the body column; wash
  hairline between turns.
- **States:** stage directions (waits, notifications, stops) mute to faint
  ink; a failing speaker's label turns signal red at weight 650. Tool calls
  collapse under a quiet `details/summary`; signatures are 11.5px mono,
  outputs hairline-left-ruled `pre` capped at 240px.

### Header colophon
- Actions ("open files", "theme") are soft bordered text buttons (7px
  radius, hairline border, panel ground), separated by faint middle dots. The muted draft line beneath
  the title is the page's citation device: it states the data's provenance
  and appends, never overwrites, when picked files join the snapshot.

### Motion (the one authored moment)
- `#content` settles on every navigation: `settle 0.22s
  cubic-bezier(0.16, 1, 0.3, 1)` (fade from `translateY(4px)`), restarted by
  reflow per render, suppressed under `prefers-reduced-motion: reduce`. No
  other animation or transition exists.

**The One Motion Rule.** The settle is the only motion in the system. New
interactions get state changes (underline darkening, wash hover), not
animation.

### Navigation model
- Three section tabs; detail views open by activating a verdict mark or row;
  `window.scrollY` is saved, the detail renders scrolled to top with a
  "← back (esc)" line, and Escape or the back link restores the section view
  at the saved scroll position.
- Data flow: the embedded snapshot loads at startup (zero clicks); dropped
  or picked files join it, cited in the draft line. Every run is its own
  timestamped file (`started_at` in the row, stamp in the filename); the
  runs table sorts newest-first with a "when" column, and re-run labels
  (e.g. "clockfix") appear beside their verdict marks.

## Do's and Don'ts

### Do:
- **Do** set all text in the system sans at 13.5px/1.55 with `tabular-nums`;
  clamp reading measures to 66–84ch.
- **Do** give every new table the evidence treatment: caption above
  ("Table N: …"), faint 11.5px header row, three 1px horizontal rules,
  right-aligned numeric columns, and a `.tnote` + dagger for qualifications.
- **Do** cite sources: any datum drawn from a file carries a faint 11.5px
  mono `.path` line.
- **Do** style new inputs as blanks — transparent, hairline underline,
  radius 0, darkening to ink on focus.
- **Do** make every interactive element focusable with the shared outline
  and Enter/Space-actionable; preserve Escape/back scroll restoration.
- **Do** define both light and dark values for any new color, keyed off the
  existing ink/paper tints.

### Don't:
- **Don't** introduce cards, chips, stat tiles, badges, colored lanes, or
  any boxed grouping — the surface's founding refusal.
- **Don't** spend red on anything but failure and fault.
- **Don't** use vertical table rules or zebra striping; keep radius on
  containers and controls only, and the one soft panel shadow as the only
  elevation.
- **Don't** set prose, labels, or numbers in monospace; it is reserved for
  code, call signatures, and paths.
- **Don't** add motion beyond the single settle, or bypass its
  reduced-motion guard.
- **Don't** reintroduce permission-gated data sources; the embedded snapshot
  (plus drop/pick) is the whole loading model.
