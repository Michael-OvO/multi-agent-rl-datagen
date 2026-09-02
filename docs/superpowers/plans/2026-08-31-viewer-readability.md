# Viewer Readability Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make each tab of `trajectory_viewer.html` read as one thing: the Runs tab says what its grid answers and folds the run list into a drawer; a grid cell holding many runs shows one mark and a count; the signal chips count runs and say so; a task's detail leads with its runs; an episode's header is three blocks, not four.

**Architecture:** Five self-contained edits to the page's hand-written JavaScript and stylesheet, one per section of spec §9, each behind source-level tests in `forge/tests/test_viewer.py`. No snapshot change, no builder change, no new colour token; disclosures reuse the page's existing `<details>` component with one new `details.drawer` style.

**Tech Stack:** One hand-written HTML/CSS/JS file; pytest. Spec: `docs/superpowers/specs/2026-08-31-viewer-current-design.md` §9 (and the §3, §5, §8 sentences it amends).

## Global Constraints

- **TDD, always.** Failing test first, watched failing, then minimal code.
- **Run everything with `.venv/bin/python`.** Never `.venv-gaia2`. While iterating: `.venv/bin/python -m pytest forge/tests/test_viewer.py -q`; before each commit: `.venv/bin/python -m pytest -q` and `.venv/bin/python -m ruff check forge scripts`.
- **The viewer stays one self-contained file**; never hand-edit the `#embedded-logs` block. Every edit uses the `Edit` tool with the exact `old_string` quoted below (all verbatim from HEAD `8679cad`). If an anchor is not found or not unique, stop and report NEEDS_CONTEXT with the text searched for — never improvise an anchor.
- **No new `--` colour token.** New CSS rules use only existing tokens (`--muted`, `--ink`, `--ink-2`, `--hair`, `--surface`). The contrast validator in `test_viewer.py` must stay untouched and green.
- **Every status is painted through `badge(kind, label)`**; a `.tag` is colourless; no tiles, cards, hero figures or motion. The header keeps exactly two actions.
- **Pre-existing tests that pin these regions must keep passing without edits** unless a step below says otherwise: `test_the_grid_tags_only_the_minority_judge` and `test_the_grid_states_the_majority_parse_and_tags_only_departures` (both anchor on the `-- Table 1: the verdict matrix --` … `-- Table 2:` comments), `test_the_signal_row_computes_what_its_chips_report`, `test_the_signal_counters_do_not_double_report`, `test_signals_are_clickable_filters`, `test_stopped_is_a_disjoint_signal_with_its_own_chip`, `test_the_runs_view_offers_a_campaign_picker_in_the_filter_line` (its asserts hold; its name is left alone), `test_a_task_detail_renders_its_instruction_as_prose_and_its_runs`, `test_the_shaping_signals_feature_survived_the_rebuild`.
- **The tests search the page through `viewer_source(viewer_html)`**, never the raw file; the CSS through the `viewer_css` fixture.
- **After every task's page edits**, run the JavaScriptCore parse check and include its output in the report:
  `.venv/bin/python -c "import re,pathlib; h=pathlib.Path('trajectory_viewer.html').read_text(); b=max(re.findall(r'<script>(.*?)</script>', h, re.S), key=len); pathlib.Path('/tmp/viewer_parse_check.js').write_text('function __p__() {\n'+b+'\n}\n\"parsed ok\";\n')" && osascript -l JavaScript /tmp/viewer_parse_check.js` — must print `parsed ok`.
- Commit subjects are sentences in the repository's style (no `feat:` prefixes), trailer `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`, `git commit -F -` with a heredoc, `git add` explicit paths only.

## File structure

| file | responsibility |
|---|---|
| `trajectory_viewer.html` (modify) | the five render changes and two small style additions |
| `forge/tests/test_viewer.py` (modify) | source-level tests for each |
| `DESIGN.md` (modify, Task 3 only) | one sentence: signal chips count runs |

---

### Task 1: The Runs tab reads as one thing (§9A)

**Files:**
- Modify: `trajectory_viewer.html` — state block, the head of `renderRuns`, the Table 2 region, the stylesheet
- Test: `forge/tests/test_viewer.py`

**Interfaces:**
- Consumes: `campaignSel`, `fullLabel`, `labels`, `campaignCounts`, `CAMPAIGN_MIN_EPISODES`, `issueFilter`, `pendingQuery`, `render()`, `$()`, `esc()` — all already in the file.
- Produces: module-level `let runsDrawerOpen = false;` and, inside `renderRuns`, a `drawer` element that Task 2's count tags open by setting `pendingQuery`.

- [ ] **Step 1: Write the failing tests**

Append to `forge/tests/test_viewer.py`:

```python
# -- §9A: the Runs tab reads as one thing -------------------------------------


def _runs_fn(viewer_html: str) -> str:
    source = viewer_source(viewer_html)
    fn = re.search(r"function renderRuns\(content\) \{(.*?)\n\}\n", source, re.S)
    assert fn, "renderRuns moved"
    return fn.group(1)


def test_the_runs_tab_says_what_its_grid_answers(viewer_html):
    body = _runs_fn(viewer_html)
    lede = body.index('<p class="lede">Every verdict for the chosen campaign')
    assert "whether a knob bit against the control" in body
    assert lede < body.index('id="campaignpick"') < body.index("-- Table 1: the verdict matrix --"), (
        "lede, then the picker on its own line, then the grid")


def test_the_run_list_is_a_drawer_under_the_grid(viewer_html):
    source = viewer_source(viewer_html)
    body = _runs_fn(viewer_html)
    assert "let runsDrawerOpen = false;" in source
    assert 'drawer.className = "drawer";' in body
    assert "drawer.open = runsDrawerOpen || !!issueFilter || !!pendingQuery;" in body
    assert "drawer.appendChild(fbar);" in body and "drawer.appendChild(twrap);" in body
    assert "content.appendChild(twrap);" not in body
    assert 'drawer.addEventListener("toggle"' in body


def test_the_drawer_summary_hides_the_native_marker_with_the_palette_s_muted(viewer_css):
    assert re.search(r"details\.drawer > summary\s*\{[^}]*list-style: none", viewer_css)
    assert re.search(r"details\.drawer > summary::-webkit-details-marker\s*\{[^}]*display: none", viewer_css)
    assert re.search(r"details\.drawer > summary::before\s*\{[^}]*var\(--muted\)", viewer_css)
    assert "details.drawer[open] > summary::before" in viewer_css
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest forge/tests/test_viewer.py -k "grid_answers or is_a_drawer or native_marker" -q`
Expected: 3 failed

- [ ] **Step 3: Add the drawer state**

Edit `trajectory_viewer.html`. Old string (verbatim):

```
let fullLabel = null;      // the campaign whose transcripts the snapshot embeds
let campaignSel = null;    // null until first render, then a label or "*" for all
```

New string:

```
let fullLabel = null;      // the campaign whose transcripts the snapshot embeds
let campaignSel = null;    // null until first render, then a label or "*" for all
let runsDrawerOpen = false; // the reader's own toggle of the run list, kept across re-renders
```

- [ ] **Step 4: The lede and the picker on its own line**

Edit `trajectory_viewer.html`. Old string (verbatim):

```
  content.insertAdjacentHTML("beforeend", `<h2 class="sec">Runs</h2>`);
  const stats = runStats(eps);
  renderSignals(content, stats);
```

New string:

```
  content.insertAdjacentHTML("beforeend", `<h2 class="sec">Runs</h2>
    <p class="lede">Every verdict for the chosen campaign, by scenario and
    configuration — read across a row to see whether a knob bit against the
    control. <b>${eps.length}</b> run${eps.length === 1 ? "" : "s"}; each is
    listed below.</p>`);

  /* The picker governs the whole tab, so it sits on its own line above
     everything it changes. 13 labels + "(unlabelled)" + "all campaigns"
     read as 15 flat entries when 8 of them are one-run probes; group
     instead of hiding anything. */
  const campaignOptionFor = l => `<option value="${esc(l)}"${
    l === campaignSel ? " selected" : ""}>${esc(l)}</option>`;
  const campaignGroup = labels.filter(l => campaignCounts.get(l) >= CAMPAIGN_MIN_EPISODES);
  const probeGroup = labels.filter(l => campaignCounts.get(l) < CAMPAIGN_MIN_EPISODES);
  const pickbar = document.createElement("div");
  pickbar.className = "filterline";
  pickbar.innerHTML = `<span>campaign
      <select id="campaignpick" aria-label="campaign">${
        campaignGroup.length
          ? `<optgroup label="campaigns">${campaignGroup.map(campaignOptionFor).join("")}</optgroup>`
          : ""}${
        probeGroup.length
          ? `<optgroup label="probes">${probeGroup.map(campaignOptionFor).join("")}</optgroup>`
          : ""}<option value="*"${
        campaignSel === "*" ? " selected" : ""}>all campaigns</option></select></span>`;
  content.appendChild(pickbar);
  /* The picker changes what the whole view computes from, so it re-renders
     rather than filtering rows; the search box and the dropdowns still
     compose on top of whichever campaign is chosen. */
  $("#campaignpick", pickbar).addEventListener("change", e => {
    campaignSel = e.target.value; issueFilter = null; pendingQuery = null; render();
  });

  const stats = runStats(eps);
  renderSignals(content, stats);
```

- [ ] **Step 5: The drawer replaces the "All runs" title and takes the filter line**

Edit `trajectory_viewer.html`. Old string (verbatim):

```
  content.insertAdjacentHTML("beforeend",
    `<div class="panel-title">All runs
       <span class="sub">— newest first; click a row for its transcript</span></div>`);
  /* 13 labels + "(unlabelled)" + "all campaigns" read as 15 flat entries
     when 8 of them are one-run probes; group instead of hiding anything. */
  const campaignOptionFor = l => `<option value="${esc(l)}"${
    l === campaignSel ? " selected" : ""}>${esc(l)}</option>`;
  const campaignGroup = labels.filter(l => campaignCounts.get(l) >= CAMPAIGN_MIN_EPISODES);
  const probeGroup = labels.filter(l => campaignCounts.get(l) < CAMPAIGN_MIN_EPISODES);
  const fbar = document.createElement("div");
  fbar.className = "filterline";
  fbar.innerHTML = `<span>campaign
      <select id="campaignpick" aria-label="campaign">${
        campaignGroup.length
          ? `<optgroup label="campaigns">${campaignGroup.map(campaignOptionFor).join("")}</optgroup>`
          : ""}${
        probeGroup.length
          ? `<optgroup label="probes">${probeGroup.map(campaignOptionFor).join("")}</optgroup>`
          : ""}<option value="*"${
        campaignSel === "*" ? " selected" : ""}>all campaigns</option></select></span>
    <span>restrict to
```

New string:

```
  /* The list is the drawer under the grid: closed by default, opened by any
     filter the reader sets (a chip, a grid count tag, a search), and by the
     reader's own toggle, which runsDrawerOpen keeps across re-renders. */
  const drawer = document.createElement("details");
  drawer.className = "drawer";
  drawer.open = runsDrawerOpen || !!issueFilter || !!pendingQuery;
  drawer.innerHTML = `<summary><span class="panel-title">every run
       <span class="sub">— newest first, filterable (${eps.length})</span></span></summary>`;
  drawer.addEventListener("toggle", () => { runsDrawerOpen = drawer.open; });
  content.appendChild(drawer);
  const fbar = document.createElement("div");
  fbar.className = "filterline";
  fbar.innerHTML = `<span>restrict to
```

Then the filter line's append and the old picker wiring. Old string (verbatim):

```
    <span class="count"></span>`;
  content.appendChild(fbar);
  /* The picker changes what the whole view computes from, so it re-renders
     rather than filtering rows; the search box and the dropdowns still
     compose on top of whichever campaign is chosen. */
  $("#campaignpick", fbar).addEventListener("change", e => {
    campaignSel = e.target.value; issueFilter = null; pendingQuery = null; render();
  });

  const hasLabels = eps.some(s => s.data.label);
```

New string:

```
    <span class="count"></span>`;
  drawer.appendChild(fbar);

  const hasLabels = eps.some(s => s.data.label);
```

Then the table's append. Old string (verbatim — the last statement of `renderRuns`):

```
  fbar.addEventListener("input", apply);
  apply();
  content.appendChild(twrap);
}

/* ================= §2 Shipped-task runs ================= */
```

New string:

```
  fbar.addEventListener("input", apply);
  apply();
  drawer.appendChild(twrap);
}

/* ================= §2 Shipped-task runs ================= */
```

- [ ] **Step 6: The drawer's summary style**

Edit `trajectory_viewer.html`. Old string (verbatim):

```
  .panel-title .sub { font-weight: 400; color: var(--ink-2); font-size: 12.5px; }
```

New string:

```
  .panel-title .sub { font-weight: 400; color: var(--ink-2); font-size: 12.5px; }
  /* A drawer: the page's disclosure component wearing a panel title. The
     native marker is hidden and a quiet glyph in --muted stands in, so the
     summary reads like the titles above it and still says it opens. */
  details.drawer { margin-top: 28px; }
  details.drawer > summary { list-style: none; cursor: pointer; width: fit-content; }
  details.drawer > summary::-webkit-details-marker { display: none; }
  details.drawer > summary::before { content: "▸"; color: var(--muted); margin-right: 7px; }
  details.drawer[open] > summary::before { content: "▾"; }
  details.drawer > summary .panel-title { display: inline; margin: 0; }
```

- [ ] **Step 7: Parse check, tests, suite, lint**

Run the JavaScriptCore parse check (Global Constraints) — expected `parsed ok`.
Run: `.venv/bin/python -m pytest forge/tests/test_viewer.py -q` — expected all passed (including the pre-existing picker and grid tests).
Run: `.venv/bin/python -m pytest -q && .venv/bin/python -m ruff check forge scripts` — expected green and clean.

- [ ] **Step 8: Commit**

```bash
git add trajectory_viewer.html forge/tests/test_viewer.py
git commit -F - <<'EOF'
Say what the grid answers, and fold the run list into a drawer under it

The Runs tab showed the same runs twice with nothing saying why. Now a lede
under the heading says what the grid is for -- read across a row to see
whether a knob bit against the control -- the campaign picker sits on its own
line because it governs the whole tab, and the run list lives in a drawer
under the grid: closed by default, opened by any filter the reader sets, and
remembering the reader's own toggle across re-renders.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
```

---

### Task 2: One mark per cell (§9B)

**Files:**
- Modify: `trajectory_viewer.html` — the grid cell in the Table 1 block, the grid note, the `.runlab` rule
- Test: `forge/tests/test_viewer.py`

**Interfaces:**
- Consumes: Task 1's drawer (opened by `pendingQuery`), `badge`, `judgeLabel`, `parseLabel`, `majorityJudge`, `majorityParse`, `shortScenario`, `sessions`, `openDetail`, `esc`.
- Produces: nothing later tasks use.

- [ ] **Step 1: Write the failing tests**

Append to `forge/tests/test_viewer.py`:

```python
# -- §9B: one mark per cell ----------------------------------------------------


def test_a_cell_with_many_runs_shows_one_mark_and_a_count(viewer_html):
    source = viewer_source(viewer_html)
    grid = re.search(
        r"-- Table 1: the verdict matrix --\s*\*/(.*?)-- Table 2:", source, re.S).group(1)
    assert "runs.length === 1" in grid
    assert 'class="xref tag count"' in grid and "data-scenario=" in grid
    assert "runs · ${passed} pass" in grid
    assert "runlab" not in source, "the per-mark run labels are retired"
    assert "A cell that holds more than one run shows its newest verdict and a count" in grid


def test_the_count_tag_opens_the_drawer_on_that_scenario(viewer_html):
    body = _runs_fn(viewer_html)
    assert 'wrap.querySelectorAll("a[data-scenario]")' in body
    assert "pendingQuery = shortScenario(a.dataset.scenario)" in body


def test_the_runlab_rule_is_gone(viewer_css):
    assert ".runlab" not in viewer_css
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest forge/tests/test_viewer.py -k "one_mark or count_tag_opens or runlab_rule" -q`
Expected: 3 failed

- [ ] **Step 3: One mark and a count**

Edit `trajectory_viewer.html`. Old string (verbatim):

```
          if (!runs.length) return `<td class="wrapok"><span class="dim">—</span></td>`;
          return `<td class="wrapok">${runs.map(s => {
            const okr = !!(s.data.verdict && s.data.verdict.success);
            const judge = s.data.judge || "scripted";
            const tag = judge !== majorityJudge
              ? `<span class="tag">${judgeLabel(judge)}</span>` : "";
            const ptag = parseLabel(s.data) !== majorityParse
              ? `<span class="tag">${esc(parseLabel(s.data))}</span>` : "";
            return `<a class="xref" data-i="${sessions.indexOf(s)}"
              tabindex="0" role="button"
              title="${esc(String(s.data.answer ?? ""))}">${
              badge(okr ? "pass" : "fail", okr ? "pass" : "fail")}${tag}${ptag}${
              runs.length > 1 && s.data.label
                ? ` <span class="runlab">${esc(s.data.label)}</span>` : ""}</a>`;
          }).join('<span class="dim"> · </span>')}</td>`;
```

New string:

```
          if (!runs.length) return `<td class="wrapok"><span class="dim">—</span></td>`;
          /* One mark per cell. A cell holding several runs shows the newest
             verdict and a colourless count that opens the run list on this
             scenario: the annotation lands only where the exception is. */
          const mark = s => {
            const okr = !!(s.data.verdict && s.data.verdict.success);
            const judge = s.data.judge || "scripted";
            const tag = judge !== majorityJudge
              ? `<span class="tag">${judgeLabel(judge)}</span>` : "";
            const ptag = parseLabel(s.data) !== majorityParse
              ? `<span class="tag">${esc(parseLabel(s.data))}</span>` : "";
            return `<a class="xref" data-i="${sessions.indexOf(s)}"
              tabindex="0" role="button"
              title="${esc(String(s.data.answer ?? ""))}">${
              badge(okr ? "pass" : "fail", okr ? "pass" : "fail")}${tag}${ptag}</a>`;
          };
          if (runs.length === 1) return `<td class="wrapok">${mark(runs[0])}</td>`;
          const passed = runs.filter(s => s.data.verdict && s.data.verdict.success).length;
          return `<td class="wrapok">${mark(runs[runs.length - 1])}
            <a class="xref tag count" data-scenario="${esc(sc)}" tabindex="0" role="button"
              title="open the run list on this scenario">${runs.length} runs · ${passed} pass</a></td>`;
```

- [ ] **Step 4: The note's sentence and the count tag's click**

Edit `trajectory_viewer.html`. Old string (verbatim):

```
      default; a mark tagged with a different judge used that judge instead.
      Two marks in one cell are the same run under both judges.
```

New string:

```
      default; a mark tagged with a different judge used that judge instead.
      A cell that holds more than one run shows its newest verdict and a count;
      the count opens the list below, filtered to that scenario.
```

Old string (verbatim):

```
  wrap.querySelectorAll("a[data-i]").forEach(a =>
    a.onclick = () => openDetail(Number(a.dataset.i)));
  content.appendChild(wrap);
```

New string:

```
  wrap.querySelectorAll("a[data-i]").forEach(a =>
    a.onclick = () => openDetail(Number(a.dataset.i)));
  wrap.querySelectorAll("a[data-scenario]").forEach(a =>
    a.onclick = () => { pendingQuery = shortScenario(a.dataset.scenario); render(); });
  content.appendChild(wrap);
```

- [ ] **Step 5: Retire the `.runlab` rule**

Edit `trajectory_viewer.html`. Old string (verbatim):

```
  .runlab { color: var(--muted); font-size: 11px; }
  .note { font-size: 12px; color: var(--muted); margin: 8px 0 0; max-width: 84ch; }
```

New string:

```
  .note { font-size: 12px; color: var(--muted); margin: 8px 0 0; max-width: 84ch; }
```

- [ ] **Step 6: Parse check, tests, suite, lint** — as in Task 1 Step 7. The pre-existing `test_the_grid_tags_only_the_minority_judge` must still find `badge(` and `majorityJudge` and no `verdictBadge(` in the block.

- [ ] **Step 7: Commit**

```bash
git add trajectory_viewer.html forge/tests/test_viewer.py
git commit -F - <<'EOF'
Show one mark per grid cell, and a count where a cell holds several runs

At "all campaigns" 149 of 174 occupied cells held more than one run and the
per-mark run labels landed on nearly every one -- the annotation had become
the rule. A cell now shows its newest verdict and a colourless count that
opens the run list on that scenario; a single-run cell is unchanged; the
run-label rule and its style are retired.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
```

---

### Task 3: Signal chips count runs and say so (§9C)

**Files:**
- Modify: `trajectory_viewer.html` — `runStats`, `renderSignals`, the `.signals` rule
- Modify: `DESIGN.md` — the Signal chip component paragraph
- Test: `forge/tests/test_viewer.py`

**Interfaces:**
- Consumes: `countMalformed`, `countErrors`, `wasStopped`, `ICONS`, `issueFilter`, `pendingQuery`.
- Produces: nothing later tasks use. `stats.malformed/blocked/errors/stopped` change meaning from calls to runs; the only consumer is `renderSignals`.

- [ ] **Step 1: Write the failing tests**

Append to `forge/tests/test_viewer.py`:

```python
# -- §9C: signal chips count runs and say so ----------------------------------


def test_run_stats_counts_runs_not_calls(viewer_html):
    source = viewer_source(viewer_html)
    body = re.search(r"function runStats\(eps\) \{(.*?)\n\}", source, re.S).group(1)
    assert "if (countMalformed(s.data)) malformed++;" in body
    assert "if (s.data.blocked) blocked++;" in body
    assert "if (countErrors(s.data)) errors++;" in body
    assert "if (wasStopped(s.data)) stopped++;" in body


def test_the_signal_row_leads_in_and_labels_every_chip_in_runs(viewer_html):
    source = viewer_source(viewer_html)
    body = re.search(r"function renderSignals\(content, stats\) \{(.*?)\n\}", source, re.S).group(1)
    assert '<span class="lab">issues in this campaign</span>' in body
    assert "with malformed line" in body and "with blocked call" in body
    assert "with faulted tool call" in body and "stopped by the world" in body
    assert "const runs = n =>" in body, "one helper pluralises 'run'"


def test_the_signal_lead_in_uses_the_credit_label_style(viewer_css):
    assert re.search(r"\.signals \.lab\s*\{[^}]*var\(--muted\)", viewer_css)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest forge/tests/test_viewer.py -k "counts_runs_not_calls or leads_in_and_labels or lead_in_uses" -q`
Expected: 3 failed

- [ ] **Step 3: Count runs in `runStats`**

Edit `trajectory_viewer.html`. Old string (verbatim):

```
function runStats(eps) {
  let malformed = 0, blocked = 0, errors = 0, stopped = 0;
  for (const s of eps) {
    malformed += countMalformed(s.data);
    blocked += s.data.blocked || 0;
    errors += countErrors(s.data);
    if (wasStopped(s.data)) stopped++;
  }
```

New string:

```
function runStats(eps) {
  /* Every chip counts RUNS -- the unit a click filters the list to. The
     per-call counters still feed the runs table's issues column. */
  let malformed = 0, blocked = 0, errors = 0, stopped = 0;
  for (const s of eps) {
    if (countMalformed(s.data)) malformed++;
    if (s.data.blocked) blocked++;
    if (countErrors(s.data)) errors++;
    if (wasStopped(s.data)) stopped++;
  }
```

- [ ] **Step 4: The lead-in and the labels**

Edit `trajectory_viewer.html`. Old string (verbatim):

```
  const signals = [];
  if (stats.malformed)
    signals.push({key: "malformed", kind: "warn",
                  label: `${stats.malformed} malformed protocol line${stats.malformed === 1 ? "" : "s"}`});
  if (stats.blocked)
    signals.push({key: "blocked", kind: "warn",
                  label: `${stats.blocked} blocked call${stats.blocked === 1 ? "" : "s"}`});
  if (stats.errors)
    signals.push({key: "errors", kind: "warn",
                  label: `${stats.errors} faulted tool call${stats.errors === 1 ? "" : "s"}`});
  if (stats.stopped)
    signals.push({key: "stopped", kind: "warn",
                  label: `${stats.stopped} stopped by the world`});
```

New string:

```
  const signals = [];
  const runs = n => `${n} run${n === 1 ? "" : "s"}`;
  if (stats.malformed)
    signals.push({key: "malformed", kind: "warn",
                  label: `${runs(stats.malformed)} with malformed lines`});
  if (stats.blocked)
    signals.push({key: "blocked", kind: "warn",
                  label: `${runs(stats.blocked)} with blocked calls`});
  if (stats.errors)
    signals.push({key: "errors", kind: "warn",
                  label: `${runs(stats.errors)} with faulted tool calls`});
  if (stats.stopped)
    signals.push({key: "stopped", kind: "warn",
                  label: `${runs(stats.stopped)} stopped by the world`});
```

Old string (verbatim):

```
  const row = document.createElement("div");
  row.className = "signals";
  row.innerHTML = signals.map(sig => `<button class="signal ${sig.kind}${
```

New string:

```
  const row = document.createElement("div");
  row.className = "signals";
  row.innerHTML = `<span class="lab">issues in this campaign</span>` +
    signals.map(sig => `<button class="signal ${sig.kind}${
```

- [ ] **Step 5: The lead-in's style**

Edit `trajectory_viewer.html`. Old string (verbatim):

```
  .signals { display: flex; flex-wrap: wrap; gap: 9px; margin: 14px 0 0; }
```

New string:

```
  .signals { display: flex; flex-wrap: wrap; gap: 9px; margin: 14px 0 0; align-items: center; }
  .signals .lab {
    font-size: 11px; font-weight: 600; color: var(--muted);
    letter-spacing: 0.02em;
  }
```

- [ ] **Step 6: DESIGN.md**

Edit `DESIGN.md`. Old string (verbatim):

```
Active chips carry the shared focus outline (`.on`). Clicking a
chip filters the runs table; clicking the "worst scenario" chip seeds the
search box with that scenario instead.
```

New string:

```
Active chips carry the shared focus outline (`.on`). Clicking a
chip filters the runs table; clicking the "worst scenario" chip seeds the
search box with that scenario instead. Every chip counts **runs** -- the unit
a click filters to -- and the row opens with a `.lab` lead-in naming the
campaign it describes; the per-call counts live in the runs table's issues
column, where a reader can see which run they belong to.
```

- [ ] **Step 7: Parse check, tests, suite, lint** — as in Task 1 Step 7. The pre-existing `test_the_signal_row_computes_what_its_chips_report`, `test_the_signal_counters_do_not_double_report`, `test_signals_are_clickable_filters` and `test_stopped_is_a_disjoint_signal_with_its_own_chip` must keep passing (the latter looks for `stopped by the world` and `key: "stopped", kind: "warn"`, both still present).

- [ ] **Step 8: Commit**

```bash
git add trajectory_viewer.html forge/tests/test_viewer.py DESIGN.md
git commit -F - <<'EOF'
Count runs on every signal chip, and say what the row is

The chips mixed units: "stopped by the world" counted runs while "faulted
tool calls" counted calls, in one row with no lead-in. Every chip now counts
runs -- the thing a click filters to -- and the row opens with "issues in
this campaign". The per-call counts keep feeding the runs table's issues
column, where they sit beside the run they belong to.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
```

---

### Task 4: Task detail, runs first (§9D)

**Files:**
- Modify: `trajectory_viewer.html` — `renderTaskDetail`
- Test: `forge/tests/test_viewer.py`

**Interfaces:**
- Consumes: Task 1's `details.drawer` style; `mdLite`, `verdictBadge`, `sessions`, `openDetail`, `esc`.
- Produces: nothing later tasks use.

- [ ] **Step 1: Write the failing test**

Append to `forge/tests/test_viewer.py`:

```python
# -- §9D: task detail, runs first ---------------------------------------------


def test_a_task_detail_leads_with_its_runs_and_folds_the_instruction_open(viewer_html):
    source = viewer_source(viewer_html)
    body = re.search(r"function renderTaskDetail\(content, s\) \{(.*?)\n\}", source, re.S).group(1)
    assert body.index("Harbor runs of this task") < body.index("mdLite("), "runs before the instruction"
    assert 'inst.className = "drawer";' in body and "inst.open = true;" in body
    assert "Instruction" in body and "what the Main is told" in body
    assert 'panel.className = "verdict-panel";' in body
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest forge/tests/test_viewer.py -k "leads_with_its_runs" -q`
Expected: 1 failed

- [ ] **Step 3: Move the instruction under the runs, in an open drawer**

Edit `trajectory_viewer.html`. Old string (verbatim):

```
  if (d.description)
    content.insertAdjacentHTML("beforeend", `<p class="lede">${esc(d.description)}</p>`);

  const panel = document.createElement("div");
  panel.className = "verdict-panel";
  panel.innerHTML = d.instruction
    ? `<div class="head">Instruction</div>${mdLite(d.instruction)}`
    : `<div class="head">Instruction</div><div>This task directory has no
       <span class="mono">instruction.md</span>.</div>`;
  content.appendChild(panel);

  const runs = d.runs || [];
```

New string:

```
  if (d.description)
    content.insertAdjacentHTML("beforeend", `<p class="lede">${esc(d.description)}</p>`);

  const runs = d.runs || [];
```

Old string (verbatim):

```
  content.insertAdjacentHTML("beforeend", `<p class="path">${esc(s.path)}</p>`);
  if ((d.files || []).length)
    content.insertAdjacentHTML("beforeend",
      `<details><summary>${d.files.length} file${d.files.length === 1 ? "" : "s"} in the task</summary>
       <pre>${esc(d.files.join("\n"))}</pre></details>`);
}
```

New string:

```
  /* The instruction is the one thing that defines a task, so it opens by
     default and folds only if the reader folds it; the runs sit above it
     because "what happened" is the question that brings a reader here. */
  const inst = document.createElement("details");
  inst.className = "drawer";
  inst.open = true;
  inst.innerHTML = `<summary><span class="panel-title">Instruction
       <span class="sub">— what the Main is told</span></span></summary>`;
  const panel = document.createElement("div");
  panel.className = "verdict-panel";
  panel.innerHTML = d.instruction
    ? mdLite(d.instruction)
    : `<div>This task directory has no <span class="mono">instruction.md</span>.</div>`;
  inst.appendChild(panel);
  content.appendChild(inst);

  content.insertAdjacentHTML("beforeend", `<p class="path">${esc(s.path)}</p>`);
  if ((d.files || []).length)
    content.insertAdjacentHTML("beforeend",
      `<details><summary>${d.files.length} file${d.files.length === 1 ? "" : "s"} in the task</summary>
       <pre>${esc(d.files.join("\n"))}</pre></details>`);
}
```

- [ ] **Step 4: Parse check, tests, suite, lint** — as in Task 1 Step 7. The pre-existing `test_a_task_detail_renders_its_instruction_as_prose_and_its_runs` must keep passing (`mdLite(`, `family match`, `verdictBadge(`, `contract <b class="mono">`, `sessions.findIndex(` all remain in the function).

- [ ] **Step 5: Commit**

```bash
git add trajectory_viewer.html forge/tests/test_viewer.py
git commit -F - <<'EOF'
Lead a task's detail with its runs; keep the instruction open beneath them

The instruction ran long and the runs table under it was easy to miss. The
runs now come first -- what happened is the question that brings a reader
here -- and the instruction sits in a drawer that opens by default, because
it is the one thing that defines a task and should fold only by choice.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
```

---

### Task 5: One signals row on an episode (§9E)

**Files:**
- Modify: `trajectory_viewer.html` — `renderEpisode` between the verdict panel and the blocked-reasons note; the `.credit` rules
- Modify: `forge/tests/test_viewer.py` — one existing test rewritten for the new shape, plus one new test

**Interfaces:**
- Consumes: `wasStopped`, `lastStop`, `esc`.
- Produces: nothing later tasks use.

- [ ] **Step 1: Rewrite the pre-existing stop-line test and add the row test**

In `forge/tests/test_viewer.py`, replace the whole function `test_a_stopped_episode_gets_one_credit_style_stop_line` (its old body asserts `line.className = "credit";`) with:

```python
def test_a_stopped_episode_gets_a_world_stopped_group_in_the_signals_row(viewer_html):
    body = _episode_fn(viewer_html)
    assert "if (wasStopped(d)) {" in body
    assert 'class="grp" title="${esc(String(st.reason || ""))}"' in body
    assert "simulated seconds used" in body
    assert "no clock recorded for this run" in body
```

Append:

```python
# -- §9E: one signals row on an episode ---------------------------------------


def test_the_episode_header_has_one_signals_row(viewer_html):
    body = _episode_fn(viewer_html)
    assert body.count('className = "credit"') == 1, "shaping signals and the stop facts share one row"
    assert 'sig.className = "credit";' in body
    assert body.count('<span class="grp"') >= 2
    assert "if (groups) {" in body


def test_signal_groups_lay_out_as_one_row(viewer_css):
    assert re.search(r"\.credit \.grp\s*\{[^}]*inline-flex", viewer_css)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest forge/tests/test_viewer.py -k "world_stopped_group or one_signals_row or lay_out_as_one_row" -q`
Expected: 3 failed

- [ ] **Step 3: One row of groups**

Edit `trajectory_viewer.html`. Old string (verbatim):

```
  /* Shaping signals sit beside the verdict, never instead of it: a partial
     reward says how much of the gold work landed, the pivot says where the
     run first went wrong. */
  if (d.credit) {
    const credit = document.createElement("div");
    credit.className = "credit";
    credit.innerHTML = `<span class="lab">shaping signals</span>
      <span>partial reward <b>${esc(String(d.credit.partial_reward))}</b></span>
      <span>coverage <b>${esc(String(d.credit.coverage))}</b></span>
      <span>fidelity <b>${esc(String(d.credit.fidelity))}</b> of
        ${esc(String(d.credit.gold_total))} gold writes</span>
      ${d.credit.pivot != null
        ? `<span class="warn-text">pivot at event ${esc(String(d.credit.pivot))}
             (${esc(d.credit.pivot_kind)}) — frozen prefix above, trainable
             suffix below</span>`
        : `<span class="dim">no located fault — the failure is missing work,
             not a wrong step</span>`}`;
    content.appendChild(credit);
  }

  /* The world's own account of the ending, beside the verdict like the
     shaping signals: how much of the horizon was spent, and the state the
     environment stopped in. Absent when the agent answered. */
  if (wasStopped(d)) {
    const st = lastStop(d);
    const line = document.createElement("div");
    line.className = "credit";
    if (st) {
      line.title = String(st.reason || "");
      line.innerHTML = `<span class="lab">world stopped</span>
        <span><b>${esc(String(Math.round(st.time_passed)))}</b>${
          st.duration != null ? ` of <b>${esc(String(Math.round(st.duration)))}</b>` : ""}
          simulated seconds used</span>
        <span>${esc(String(st.env_state || ""))}</span>`;
    } else {
      line.innerHTML = `<span class="lab">world stopped</span>
        <span class="dim">no clock recorded for this run</span>`;
    }
    content.appendChild(line);
  }
```

New string:

```
  /* One signals row beside the verdict, never instead of it: the shaping
     signals (how much of the gold work landed, where the run first went
     wrong) and, when the world ended the run, its own account of the ending
     -- as labelled groups on one line, so the header is three blocks. */
  let groups = "";
  if (d.credit)
    groups += `<span class="grp"><span class="lab">shaping signals</span>
      <span>partial reward <b>${esc(String(d.credit.partial_reward))}</b></span>
      <span>coverage <b>${esc(String(d.credit.coverage))}</b></span>
      <span>fidelity <b>${esc(String(d.credit.fidelity))}</b> of
        ${esc(String(d.credit.gold_total))} gold writes</span>
      ${d.credit.pivot != null
        ? `<span class="warn-text">pivot at event ${esc(String(d.credit.pivot))}
             (${esc(d.credit.pivot_kind)}) — frozen prefix above, trainable
             suffix below</span>`
        : `<span class="dim">no located fault — the failure is missing work,
             not a wrong step</span>`}</span>`;
  if (wasStopped(d)) {
    const st = lastStop(d);
    groups += st
      ? `<span class="grp" title="${esc(String(st.reason || ""))}"><span class="lab">world stopped</span>
        <span><b>${esc(String(Math.round(st.time_passed)))}</b>${
          st.duration != null ? ` of <b>${esc(String(Math.round(st.duration)))}</b>` : ""}
          simulated seconds used</span>
        <span>${esc(String(st.env_state || ""))}</span></span>`
      : `<span class="grp"><span class="lab">world stopped</span>
        <span class="dim">no clock recorded for this run</span></span>`;
  }
  if (groups) {
    const sig = document.createElement("div");
    sig.className = "credit";
    sig.innerHTML = groups;
    content.appendChild(sig);
  }
```

- [ ] **Step 4: The group style**

Edit `trajectory_viewer.html`. Old string (verbatim):

```
  .credit b { color: var(--ink); font-weight: 650; }
```

New string:

```
  .credit b { color: var(--ink); font-weight: 650; }
  .credit .grp {
    display: inline-flex; flex-wrap: wrap; gap: 5px 12px; align-items: baseline;
    padding-right: 6px;
  }
```

- [ ] **Step 5: Parse check, tests, suite, lint** — as in Task 1 Step 7. The pre-existing `test_the_shaping_signals_feature_survived_the_rebuild` (`d.credit` in source) and `test_an_index_stub_renders_a_summary_and_no_transcript` must keep passing.

- [ ] **Step 6: Commit**

```bash
git add trajectory_viewer.html forge/tests/test_viewer.py
git commit -F - <<'EOF'
Put an episode's shaping signals and its ending on one row

The header stacked four blocks before the transcript: run bar, verdict,
shaping signals, and -- when the world ended the run -- its stop facts. The
last two are now labelled groups on one signals row, with the environment's
own reason as the stop group's title. Three blocks, nothing dropped.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
```

---

### Task 6: The real snapshot, and the page in a browser

**Files:**
- Modify: `trajectory_viewer.html` (its `#embedded-logs` block, by running the script — never by hand)

- [ ] **Step 1: Rebuild the snapshot** — the hand-written source changed, and the shipped page must carry the final source with a current snapshot.

Run: `.venv/bin/python -m scripts.embed_logs` — expected one `viewer:` line naming 613 episodes, 10 tasks, transcripts for v6, under 8 MB.

- [ ] **Step 2: Suite and lint** — `.venv/bin/python -m pytest -q && .venv/bin/python -m ruff check forge scripts`, expected green and clean.

- [ ] **Step 3: Browser checklist (a human, from `file://`)**

1. Runs opens with the lede, then the campaign picker on its own line, then the *issues in this campaign* chips, then the grid; the run list is a closed drawer *every run — newest first, filterable (126)* under the grid's note.
2. Clicking a chip opens the drawer with the table filtered; clicking the chip again clears the filter (the drawer stays open if you opened it).
3. *All campaigns*: a multi-run cell shows one badge and a *N runs · P pass* tag; clicking the tag opens the drawer searched to that scenario.
4. Tasks → any AppWorld `2a163ab_1` task: runs table first, then the open *Instruction* drawer; folding it stays folded until re-render.
5. Any v6 stopped episode: one signals row with two groups under the verdict; hover the *world stopped* group for the reason.
6. Theme toggle across the drawer summaries and the signal lead-in.

- [ ] **Step 4: Commit**

```bash
git add trajectory_viewer.html
git commit -F - <<'EOF'
Ship the readability pass with a current snapshot

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
```

---

## Self-review

**Spec coverage.** §9A → Task 1 (lede, picker line, drawer, `runsDrawerOpen`, summary style). §9B → Task 2 (one mark, count tag, note sentence, `.runlab` retired). §9C → Task 3 (run counts, lead-in, labels, DESIGN.md sentence). §9D → Task 4 (runs first, open drawer). §9E → Task 5 (one `.credit` row of groups). §3/§5/§8 amended sentences are honoured by Tasks 1, 5 and 4 respectively. The Verification bullets for §9 map one-to-one onto the tests in Tasks 1–5. Task 6 ships the page.

**Placeholders.** None: every step carries its code, its command and its expected outcome.

**Type consistency.** `runsDrawerOpen` is declared in Task 1 and read only there; `drawer` is a local of `renderRuns` that Task 2 reaches only through `pendingQuery` (already module-level); `stats.malformed/blocked/errors/stopped` keep their names and change meaning in one producer (`runStats`) and one consumer (`renderSignals`), both in Task 3; `inst`/`panel` in Task 4 are locals; Task 5's `groups`/`sig` are locals and the rewritten test asserts the new `title` binding verbatim. The `_runs_fn` helper is defined in Task 1's tests and reused by Task 2's; `_episode_fn` already exists from the earlier plan.
