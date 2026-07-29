# Run Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn `trajectory_viewer.html` from an academic-paper "evidence page" into a run dashboard where totals, success rate, failure signals, and models are readable at a glance, and an opened run's transcript is easy to follow.

**Architecture:** The viewer stays exactly what it is — one self-contained HTML file with an inline `<style>` block, an inline `<script>` app, and an embedded JSON snapshot of the repo's logs. No build step, no dependencies, no new data sources. The work is: (1) swap the color system for the validated dataviz status palette, (2) add an overview band of stat tiles above the existing tables, (3) restyle verdict marks as badges and add a models column, (4) rebuild the transcript renderer, (5) rewrite `DESIGN.md`. A new pytest file, `forge/tests/test_viewer.py`, holds the contract tests — including WCAG contrast math computed in Python, since Node.js is unavailable on this machine and the dataviz validator cannot run here.

**Tech Stack:** Plain HTML/CSS/JavaScript (no framework, no bundler, ES2020 in-browser). Python 3 + pytest for contract tests, run via `uv run pytest`. Chrome (via the claude-in-chrome MCP tools) for visual verification.

## Global Constraints

These apply to **every** task. Copy them into your working memory before starting any task.

- **One file, self-contained.** `trajectory_viewer.html` must keep working when opened directly from disk with `file://`. No external stylesheets, scripts, fonts, or images. No network requests. No build step.
- **Do not touch the embedded snapshot.** The `<script type="application/json" id="embedded-logs">…</script>` block and its exact opening/closing tags must survive unchanged, because `scripts/embed_logs.py` rewrites it with the regex `(<script type="application/json" id="embedded-logs">).*?(</script>)`. Never hand-edit the JSON payload.
- **Data loading is unchanged.** Embedded snapshot at startup, plus drag-and-drop and the "open files" picker. No new data sources, no permission-gated APIs.
- **Status colors never carry meaning alone.** Every status color ships with an icon *and* a text label. This is non-negotiable — light-mode warning sits at 1.74:1 contrast by design.
- **Exact palette values** (validated; do not substitute or invent shades):
  - Light: `--surface #fcfcfb`, `--plane #f9f9f7`, `--ink #0b0b0b`, `--ink-2 #52514e`, `--muted #898781`, `--grid #e1e0d9`, `--axis #c3c2b7`
  - Dark: `--surface #1a1a19`, `--plane #0d0d0d`, `--ink #ffffff`, `--ink-2 #c3c2b7`, `--muted #898781`, `--grid #2c2c2a`, `--axis #383835`
  - Status marks (both modes): `--pass #0ca30c`, `--warn #fab219`, `--fail #d03b3b`
  - Status text light: `--pass-ink #006300`, `--warn-ink #8a5a00`, `--fail-ink #b42318`
  - Status text dark: `--pass-ink #3ecb4a`, `--warn-ink #fab219`, `--fail-ink #f2655c`
- **`--muted` is for de-emphasized labels only** (timestamps, table headers, axis-like text) — never body prose. It measures 3.41:1 in light mode.
- **Both themes are first-class.** Every token gets a value in three scopes: `:root` (light), `@media (prefers-color-scheme: dark) :root:not([data-theme="light"])`, and `:root[data-theme="dark"]`. The manual toggle must beat the OS setting in both directions.
- **Keyboard parity is preserved.** Tabs, grid marks, table rows, filters, and collapsible tool calls stay focusable with a visible focus outline and Enter/Space-actionable. The existing global `keydown` handler and Escape-to-close-detail behavior must keep working.
- **Exactly one hero figure per view** (the ≥48px number). It is the Runs success rate. Everything else is a normal stat tile.
- **`tabular-nums` in table columns only.** Stat-tile values and the hero figure use default proportional figures.
- **Run the full test file after every task**, not just the new test: `uv run pytest forge/tests/test_viewer.py -v`.
- **A test that asserts a string is ABSENT must search `viewer_source(viewer_html)`, never `viewer_html`.** That helper (added in Task 0) strips the embedded JSON snapshot, which carries arbitrary prose lifted from run transcripts and will otherwise produce false hits. Tests asserting a string is *present* may use either.

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `trajectory_viewer.html` | The entire dashboard: `<style>` tokens + component CSS (lines ~38–267), `<body>` skeleton (~269–282), embedded snapshot (~283), inline app `<script>` (~284–963) | Modify throughout |
| `forge/tests/test_viewer.py` | Contract tests: palette tokens exist in all three theme scopes, computed WCAG contrast, snapshot-block drift guard, presence of each dashboard component | Create (Task 1), extend in later tasks |
| `DESIGN.md` | The design system document for the viewer | Rewrite (Task 8) |

The app script keeps its current section layout — plumbing, shared pieces, top-level render, §1 Runs, §2 Shipped-task runs, §3 Evidence files, run detail, breakdown detail, startup. New helpers go in the "shared pieces" section so every renderer can use them.

**A note on line numbers.** This plan names blocks by their *content anchors*, never by line number. The file's line numbering shifts as tasks land, and it changed once already between planning and execution. Find blocks by searching for the quoted text.

---

### Task 0: Remove the folder-connect layer

The file currently loads data two ways: an embedded snapshot *and* a live connection to the repository folder through the File System Access API, with the directory handle retained in IndexedDB. The approved spec keeps only the snapshot (plus drag-and-drop and the file picker), and the user confirmed that choice on 2026-07-28. Removing this layer first is what makes the rest of the plan apply cleanly — every later task assumes the snapshot-only file.

Do not treat this as a refactor to preserve behavior. The permission-gated data source is being deleted on purpose.

**Files:**
- Create: `forge/tests/test_viewer.py`
- Modify: `trajectory_viewer.html` (the `<!-- … -->` thesis comment, the `<header>` markup, the state block, the folder-connect functions, the empty state, the startup block)

**Interfaces:**
- Consumes: nothing (first task)
- Produces:
  - The pytest fixtures `viewer_html` and `viewer_css`, the helpers `contrast()` and `theme_scopes()`, and the module constant `_GROUNDS` — Task 1 appends to this file and uses all of them.
  - A viewer whose only startup path is `loadSnapshot()`, whose header holds exactly two actions ("open files", "theme"), and whose module-level `sourceLine` still drives `#draftline`.

- [ ] **Step 1: Write the failing test**

Create `forge/tests/test_viewer.py`:

```python
"""The viewer is one HTML file, so these are its contract tests.

`trajectory_viewer.html` has no build step and no unit-testable modules: its
CSS and JavaScript live inline. What can be checked here is the part that is
computable rather than visual -- that the loading model is the one the spec
approved, that every design token exists in all three theme scopes, and that
the colors clear WCAG contrast against the grounds they actually render on.
Node.js is not installed on the build machine, so the dataviz skill's palette
validator cannot run; this file carries the contrast math instead.

Layout, spacing, and "does it look right" are verified in a browser, not here.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_VIEWER = _ROOT / "trajectory_viewer.html"

#: Light and dark grounds a color may be painted on. Text must clear its
#: threshold against BOTH grounds of its own mode -- the plane is the darker
#: ground in light mode, the surface is the lighter one in dark mode.
_GROUNDS = {"light": ("#fcfcfb", "#f9f9f7"), "dark": ("#1a1a19", "#0d0d0d")}


@pytest.fixture(scope="module")
def viewer_html() -> str:
    return _VIEWER.read_text()


@pytest.fixture(scope="module")
def viewer_css(viewer_html: str) -> str:
    return re.search(r"<style>(.*?)</style>", viewer_html, re.S).group(1)


def _relative_luminance(hex_color: str) -> float:
    raw = hex_color.lstrip("#")
    channels = [int(raw[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
              for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a: str, b: str) -> float:
    """WCAG 2.x contrast ratio between two opaque hex colors."""
    hi, lo = sorted((_relative_luminance(a), _relative_luminance(b)),
                    reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def theme_scopes(css: str) -> dict[str, dict[str, str]]:
    """Token tables for the three scopes the viewer must define.

    'light' is the bare `:root` block; 'dark-os' is the one inside the
    prefers-color-scheme media query; 'dark-toggle' is the `data-theme`
    override. All three carry no nested braces, so a non-greedy match to the
    first `}` is exact.
    """
    scopes = {
        "light": r":root\s*\{(.*?)\}",
        "dark-os": r':root:not\(\[data-theme="light"\]\)\s*\{(.*?)\}',
        "dark-toggle": r':root\[data-theme="dark"\]\s*\{(.*?)\}',
    }
    out = {}
    for name, pattern in scopes.items():
        block = re.search(pattern, css, re.S)
        assert block, f"the {name} theme scope is missing from the stylesheet"
        out[name] = dict(re.findall(r"(--[a-z0-9-]+)\s*:\s*([^;]+);",
                                    block.group(1)))
    return out


#: Every identifier the File System Access layer was built from. The spec
#: retired that data source: the page carries its own snapshot, so opening
#: the file is the whole workflow and no permission prompt stands in front
#: of it.
_FOLDER_CONNECT_RELICS = [
    "showDirectoryPicker", "indexedDB", "queryPermission", "requestPermission",
    "openHandleDb", "connectRepository", "refreshRepository", "liveHandle",
    "folderpick", 'id="connect"', "DB_NAME", "webkitdirectory",
]


def test_the_folder_connect_layer_is_gone(viewer_html):
    """One loading model: the embedded snapshot, plus drop and pick."""
    body = viewer_html.split('<script type="application/json"')[0] \
        + viewer_html.split("</script>")[-1]
    survivors = [relic for relic in _FOLDER_CONNECT_RELICS if relic in body]
    assert not survivors, f"folder-connect machinery survives: {survivors}"


def test_the_snapshot_is_the_startup_path(viewer_html):
    assert "function loadSnapshot()" in viewer_html


def test_the_header_offers_exactly_two_actions(viewer_html):
    header = re.search(r"<header>(.*?)</header>", viewer_html, re.S)
    assert header, "the page header is missing"
    assert header.group(1).count("<button") + header.group(1).count("<label") == 2, (
        "the header's actions are 'open files' and 'theme' -- nothing else")


def test_embed_logs_block_still_matches_its_rewriter(viewer_html):
    """`scripts.embed_logs` rewrites the snapshot by regex; keep them agreed."""
    pattern = re.compile(
        r'(<script type="application/json" id="embedded-logs">).*?(</script>)',
        re.S)
    assert len(pattern.findall(viewer_html)) == 1
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest forge/tests/test_viewer.py -v`

Expected: FAIL — `test_the_folder_connect_layer_is_gone` lists the surviving identifiers, and `test_the_header_offers_exactly_two_actions` counts three.

- [ ] **Step 3: Replace the header markup**

Find the `<header>` block in the body and replace it with:

```html
  <header>
    <h1>Trajectory evidence</h1>
    <p class="draftline" id="draftline">multi-agent-rl-datagen — no data loaded</p>
    <p class="colophon">
      <label for="pick" tabindex="0" role="button">open files</label><input id="pick" type="file" accept=".json,application/json" multiple><span class="sep">·</span><button id="theme">theme</button>
    </p>
  </header>
```

- [ ] **Step 4: Delete the folder-connect machinery from the script**

Remove every function, state variable, and event wiring that exists only to serve the live repository connection. Work by identifier — the list in `_FOLDER_CONNECT_RELICS` is exhaustive for the JavaScript, and each name's definition and every call site go together.

The state block currently declares `manualArtifacts`, `liveHandle`, `liveCache`, `liveRefresh`, and `lastLiveLoad` alongside `sessions`. Keep `sessions`; delete the rest **only if** nothing outside the removed layer reads them. Check each with a search before deleting it.

Some helpers in that region serve both the removed layer and the surviving file-picker path — `artifact`, `activateArtifacts`, `artifactCounts`, `countLine`, `relativeRepoPath`, and `wantedRepoPath` among them. Decide each on evidence, not on its neighborhood: if the drag-and-drop and "open files" paths still call it, keep it; if its only callers were the folder-connect functions, delete it. After the deletions, the manual paths must still work — a dropped file and a picked file both land in `sessions` and appear in the tables.

The end state for loading is exactly this: `loadSnapshot()` runs at startup and reads the embedded block; `addFiles()` handles both the picker's `change` event and the body's `drop` event; `sourceLine` is a plain module-level string that `render()` writes into `#draftline`.

- [ ] **Step 5: Restore the snapshot-only startup block**

The startup block at the end of the script must read:

```js
/* ================= startup: the embedded snapshot ================= */
/* Last in the file on purpose: it renders immediately, so everything it
   touches must already be declared. */

(function loadSnapshot() {
  const el = document.getElementById("embedded-logs");
  if (el) {
    let snap = null;
    try { snap = JSON.parse(el.textContent); } catch { snap = null; }
    if (snap && Array.isArray(snap.files) && snap.files.length) {
      for (const f of snap.files) addSession(f.path.split("/").pop(), f.path, f.data);
      sourceLine = `snapshot of ${snap.generated}, ${snap.files.length} artifacts`;
      sortSessions();
    }
  }
  render();
})();
```

- [ ] **Step 6: Fix the empty state and the thesis comment**

The empty state currently tells the reader to "Choose *connect repository* once and select the …". Replace that paragraph's guidance with the snapshot instruction:

```js
      <p>This file carries a snapshot of the repository's logs inside itself;
      this copy's snapshot is empty. Refresh it with
      <code>uv run python -m scripts.embed_logs</code>, or drop trajectory
      JSON files anywhere on this page (or use <i>open files</i> above).</p>
```

In the `<!-- … -->` comment at the top of the file, replace the "Auto-loading" paragraph — the one describing the File System Access API and the retained IndexedDB handle — with:

```
Auto-loading: the page carries its data — a JSON snapshot of every log
artifact sits in the #embedded-logs block, so opening the file is the whole
workflow; refresh the snapshot with `uv run python -m scripts.embed_logs`.
Supplementary files can be dropped on the page or opened via the quiet
"open files" link. Recognized shapes: gaia2 episodes, sidecar breakdowns,
sweep row files.
```

Leave the rest of the comment alone; Task 8 rewrites it wholesale.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `uv run pytest forge/tests/test_viewer.py -v`

Expected: PASS, 4 tests.

- [ ] **Step 8: Verify in the browser that nothing regressed**

Open `trajectory_viewer.html` in Chrome. The snapshot must load with zero clicks: the draft line reads "snapshot of 2026-07-28 12:59, 64 artifacts" and all three tabs populate. There is no "choose repository folder" button and no permission prompt. Open the developer console and confirm **no errors** — a missed `$("#connect")` reference throws on a null element and would silently stop the script. Drop a JSON file from `output/rollouts/` onto the page and confirm the draft line appends rather than overwrites.

- [ ] **Step 9: Commit**

```bash
git add forge/tests/test_viewer.py trajectory_viewer.html
git commit -m "Retire the folder connection; the snapshot is the loading model"
```

---

### Task 1: Palette swap

Replace the paper/single-red color system with the validated status palette.

**Files:**
- Modify: `forge/tests/test_viewer.py` (append; Task 0 created it)
- Modify: `trajectory_viewer.html` — the three theme scopes at the top of the `<style>` block, then every rule that referenced the retired token names

**Interfaces:**
- Consumes: the fixtures `viewer_html` / `viewer_css` and the helpers `contrast()` / `theme_scopes()` / `_GROUNDS`, all created in Task 0
- Produces: CSS custom properties every later task uses — `--surface`, `--plane`, `--ink`, `--ink-2`, `--muted`, `--grid`, `--axis`, `--hair`, `--wash`, `--shadow`, `--pass`, `--warn`, `--fail`, `--pass-ink`, `--warn-ink`, `--fail-ink`, `--pass-tint`, `--warn-tint`, `--fail-tint`

- [ ] **Step 1: Write the failing test**

Append to `forge/tests/test_viewer.py` (the fixtures and helpers it uses already exist there):

```python
#: Every token the dashboard is built from. A later task that needs a new
#: token adds it here first.
REQUIRED_TOKENS = [
    "--surface", "--plane", "--ink", "--ink-2", "--muted", "--grid", "--axis",
    "--hair", "--wash", "--shadow",
    "--pass", "--warn", "--fail",
    "--pass-ink", "--warn-ink", "--fail-ink",
    "--pass-tint", "--warn-tint", "--fail-tint",
]


def test_every_token_is_defined_in_all_three_theme_scopes(viewer_css):
    scopes = theme_scopes(viewer_css)
    for scope_name, tokens in scopes.items():
        missing = [t for t in REQUIRED_TOKENS if t not in tokens]
        assert not missing, f"{scope_name} scope is missing {missing}"


def test_the_two_dark_scopes_agree(viewer_css):
    """A viewer whose toggle and OS setting disagree is two designs."""
    scopes = theme_scopes(viewer_css)
    for token in REQUIRED_TOKENS:
        assert scopes["dark-os"][token].strip() == scopes["dark-toggle"][token].strip(), (
            f"{token} differs between the OS-dark and toggle-dark scopes")


@pytest.mark.parametrize("mode,scope", [("light", "light"), ("dark", "dark-toggle")])
def test_status_text_colors_clear_body_text_contrast(viewer_css, mode, scope):
    """Status *text* is read, so it needs 4.5:1 on both of its grounds."""
    tokens = theme_scopes(viewer_css)[scope]
    for token in ("--pass-ink", "--warn-ink", "--fail-ink"):
        color = tokens[token].strip()
        worst = min(contrast(color, ground) for ground in _GROUNDS[mode])
        assert worst >= 4.5, (
            f"{mode} {token} ({color}) is {worst:.2f}:1 -- body text needs 4.5:1")


@pytest.mark.parametrize("mode,scope", [("light", "light"), ("dark", "dark-toggle")])
def test_pass_and_fail_marks_clear_non_text_contrast(viewer_css, mode, scope):
    """Dots, rails, and tint borders are non-text marks: 3:1."""
    tokens = theme_scopes(viewer_css)[scope]
    for token in ("--pass", "--fail"):
        color = tokens[token].strip()
        worst = min(contrast(color, ground) for ground in _GROUNDS[mode])
        assert worst >= 3.0, (
            f"{mode} {token} ({color}) is {worst:.2f}:1 -- marks need 3:1")


def test_warning_is_the_documented_low_contrast_exception(viewer_css):
    """`--warn` is sub-3:1 on light by design.

    The dataviz reference palette ships it that way and mitigates with the
    icon + label pairing. This test pins the exception so nobody "fixes" the
    hex and quietly breaks the palette's validated CVD separation.
    """
    light = theme_scopes(viewer_css)["light"]["--warn"].strip()
    assert light == "#fab219"
    assert min(contrast(light, g) for g in _GROUNDS["light"]) < 3.0
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest forge/tests/test_viewer.py -v`

Expected: FAIL. `test_every_token_is_defined_in_all_three_theme_scopes` fails because the stylesheet still defines `--paper`, `--red`, and friends rather than the new token names. Several other tests fail on `KeyError`.

- [ ] **Step 3: Replace the three theme scopes**

In `trajectory_viewer.html`, replace everything from `:root {` down to the closing brace of the `@media (prefers-color-scheme: dark)` block (currently lines 39–80) with:

```css
  /* Design tokens. The status palette is the dataviz reference instance:
     mark colors carry state on dots and rails, the -ink variants are the
     text-safe steps (>=4.5:1 on both grounds of their mode), and the -tint
     variants are the badge and panel fills. `--warn` is deliberately
     sub-3:1 on light -- the icon + label pairing is the mitigation, so a
     status color never carries meaning by itself. */
  :root {
    color-scheme: light;
    --surface: #fcfcfb;
    --plane:   #f9f9f7;
    --ink:     #0b0b0b;
    --ink-2:   #52514e;
    --muted:   #898781;   /* 3.41:1 -- de-emphasized labels only, never prose */
    --grid:    #e1e0d9;
    --axis:    #c3c2b7;
    --hair:    rgba(11, 11, 11, 0.10);
    --wash:    rgba(11, 11, 11, 0.035);
    --shadow:  0 1px 2px rgba(11, 11, 11, 0.06);
    --pass:      #0ca30c;
    --warn:      #fab219;
    --fail:      #d03b3b;
    --pass-ink:  #006300;
    --warn-ink:  #8a5a00;
    --fail-ink:  #b42318;
    --pass-tint: rgba(12, 163, 12, 0.10);
    --warn-tint: rgba(250, 178, 25, 0.16);
    --fail-tint: rgba(208, 59, 59, 0.10);
  }
  :root[data-theme="dark"] {
    color-scheme: dark;
    --surface: #1a1a19;
    --plane:   #0d0d0d;
    --ink:     #ffffff;
    --ink-2:   #c3c2b7;
    --muted:   #898781;
    --grid:    #2c2c2a;
    --axis:    #383835;
    --hair:    rgba(255, 255, 255, 0.10);
    --wash:    rgba(255, 255, 255, 0.05);
    --shadow:  0 1px 2px rgba(0, 0, 0, 0.4);
    --pass:      #0ca30c;
    --warn:      #fab219;
    --fail:      #d03b3b;
    --pass-ink:  #3ecb4a;
    --warn-ink:  #fab219;
    --fail-ink:  #f2655c;
    --pass-tint: rgba(12, 163, 12, 0.16);
    --warn-tint: rgba(250, 178, 25, 0.16);
    --fail-tint: rgba(208, 59, 59, 0.20);
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      color-scheme: dark;
      --surface: #1a1a19;
      --plane:   #0d0d0d;
      --ink:     #ffffff;
      --ink-2:   #c3c2b7;
      --muted:   #898781;
      --grid:    #2c2c2a;
      --axis:    #383835;
      --hair:    rgba(255, 255, 255, 0.10);
      --wash:    rgba(255, 255, 255, 0.05);
      --shadow:  0 1px 2px rgba(0, 0, 0, 0.4);
      --pass:      #0ca30c;
      --warn:      #fab219;
      --fail:      #d03b3b;
      --pass-ink:  #3ecb4a;
      --warn-ink:  #fab219;
      --fail-ink:  #f2655c;
      --pass-tint: rgba(12, 163, 12, 0.16);
      --warn-tint: rgba(250, 178, 25, 0.16);
      --fail-tint: rgba(208, 59, 59, 0.20);
    }
  }
```

- [ ] **Step 4: Repoint the rest of the stylesheet at the new token names**

The old names are gone, so every use must be updated. In the remainder of the `<style>` block, apply these substitutions:

- `var(--paper)` → `var(--plane)`
- `var(--red)` → `var(--fail-ink)`
- `var(--faint)` → `var(--muted)`
- `var(--panel)` → `var(--surface)`
- `var(--rule)` → `var(--axis)`

`--ink`, `--ink-2`, `--hair`, `--wash`, and `--shadow` keep their names and need no edit. Then verify no stale references remain:

```bash
grep -nE "var\(--(paper|red|faint|panel|rule)\)" trajectory_viewer.html
```

Expected: no output.

- [ ] **Step 5: Repoint the JavaScript's inline color references**

The app script writes a few colors inline. Replace every occurrence of `style="color:var(--faint)"` with `class="dim"`, and add this rule to the stylesheet next to the `.bad` rule:

```css
  .dim { color: var(--muted); }
```

Verify:

```bash
grep -n "var(--faint)\|var(--paper)\|var(--red)" trajectory_viewer.html
```

Expected: no output.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest forge/tests/test_viewer.py -v`

Expected: PASS, 11 tests (the two parametrized tests contribute two cases each).

- [ ] **Step 7: Look at it in a browser**

Open `trajectory_viewer.html` in Chrome. Confirm the page still renders its tables, the theme toggle still flips light↔dark, and nothing is invisible or unstyled. It will still look like the old design — only the colors have moved. This step is a smoke check, not the visual review.

- [ ] **Step 8: Commit**

```bash
git add forge/tests/test_viewer.py trajectory_viewer.html
git commit -m "Swap the viewer palette for the validated status system"
```

---

### Task 2: The verdict badge

Replace typeset verdict text (`✓ success` in ink, `✗ failure` in red, dagger footnote) with a colored badge carrying icon + label. Every table in the app uses it, so it lands before they do.

**Files:**
- Modify: `trajectory_viewer.html` — add badge CSS after the `.dim` rule; replace `verdictText()` in the "shared pieces" section
- Modify: `forge/tests/test_viewer.py`

**Interfaces:**
- Consumes: `--pass-tint`, `--fail-tint`, `--warn-tint`, `--pass-ink`, `--fail-ink`, `--warn-ink` from Task 1
- Produces:
  - `verdictBadge(ok: boolean, judge?: string) -> string` — HTML for a pass/fail badge. Replaces the old `verdictText`. When `judge` is present and not `"scripted"`, appends a separate `soft judge` tag.
  - `badge(kind: "pass"|"fail"|"warn", label: string) -> string` — the general builder.
  - CSS classes `.badge`, `.badge.pass`, `.badge.fail`, `.badge.warn`, `.tag`

- [ ] **Step 1: Write the failing test**

Append to `forge/tests/test_viewer.py`:

```python
def test_verdict_badges_pair_every_color_with_an_icon_and_a_word(viewer_html):
    """The founding accessibility rule: color is never the only channel."""
    builder = re.search(r"function badge\(kind, label\) \{(.*?)\n\}",
                        viewer_html, re.S)
    assert builder, "badge() builder is missing"
    body = builder.group(1)
    assert "ICONS[kind]" in body, "the badge must render an icon"
    assert "esc(label)" in body, "the badge must render an escaped text label"
    assert 'aria-hidden="true"' in body, (
        "the icon is decorative next to its label; hide it from readers")


def test_the_dagger_footnote_is_gone(viewer_html):
    """Soft-judged runs get a readable tag, not a symbol you must decode."""
    assert '<span class="dag">' not in viewer_source(viewer_html)
    assert "soft judge" in viewer_html
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest forge/tests/test_viewer.py -v`

Expected: FAIL — `test_verdict_badges_pair_every_color_with_an_icon_and_a_word` fails with "badge() builder is missing".

- [ ] **Step 3: Add the badge CSS**

Add to the stylesheet, right after the `.dim` rule:

```css
  /* ---------- status badges: color + icon + word, always all three ---------- */
  .badge {
    display: inline-flex; align-items: center; gap: 5px;
    padding: 2px 9px; border-radius: 999px;
    font-size: 12px; font-weight: 600; white-space: nowrap;
    line-height: 1.5;
  }
  .badge .ic { font-size: 11px; line-height: 1; }
  .badge.pass { background: var(--pass-tint); color: var(--pass-ink); }
  .badge.fail { background: var(--fail-tint); color: var(--fail-ink); }
  .badge.warn { background: var(--warn-tint); color: var(--warn-ink); }
  .tag {
    display: inline-block; margin-left: 6px; padding: 1px 7px;
    border-radius: 999px; border: 1px solid var(--hair);
    font-size: 11px; color: var(--ink-2); white-space: nowrap;
  }
```

- [ ] **Step 4: Replace `verdictText` with the badge builders**

In the "shared pieces" section, replace the whole `verdictText` function (and its comment) with:

```js
/* Status is carried by three channels at once -- color, icon, and word --
   so it survives colorblindness, grayscale printing, and forced-colors. */
const ICONS = {pass: "✓", fail: "✕", warn: "▲"};

function badge(kind, label) {
  return `<span class="badge ${kind}"><span class="ic" aria-hidden="true">${
    ICONS[kind]}</span>${esc(label)}</span>`;
}

function verdictBadge(ok, judge) {
  const soft = judge && judge !== "scripted"
    ? `<span class="tag">soft judge</span>` : "";
  return badge(ok ? "pass" : "fail", ok ? "pass" : "fail") + soft;
}
```

- [ ] **Step 5: Update every caller**

`verdictText` had four call sites. Replace each:

- In `renderRuns`, inside the Table 1 grid cell builder: `verdictText(okr, s.data.judge)` → `verdictBadge(okr, s.data.judge)`
- In `renderRuns`, in the all-runs row builder: `verdictText(okr, d.judge)` → `verdictBadge(okr, d.judge)`
- In `renderBreakdowns`: `verdictText(okr)` → `verdictBadge(okr)`
- In `renderEpisode` and `renderBreakdownDetail` headings: `verdictText(okr, d.judge)` / `verdictText(!!d.success)` → `verdictBadge(...)` with the same arguments

Then confirm none survive:

```bash
grep -n "verdictText" trajectory_viewer.html
```

Expected: no output.

- [ ] **Step 6: Delete the dagger machinery**

Remove the `.dag` CSS rule. Remove the dagger sentence from the Table 1 note in `renderRuns` — replace the `${softCount ? \`† judged by …\` : ""}` interpolation with:

```js
${softCount ? ` Runs tagged <i>soft judge</i> were scored by Gaia2's official
  soft judge (gpt-5.6-sol as checker); the rest use the deterministic scripted
  judge. Two marks in one cell are the same run under both judges.` : ""}
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `uv run pytest forge/tests/test_viewer.py -v`

Expected: PASS, 13 tests.

- [ ] **Step 8: Verify in the browser**

Open the file in Chrome. Every verdict in every table is now a pill badge: green `✓ pass`, red `✕ fail`. Soft-judged runs carry a `soft judge` tag. Toggle the theme and confirm both read clearly.

- [ ] **Step 9: Commit**

```bash
git add trajectory_viewer.html forge/tests/test_viewer.py
git commit -m "Typeset verdicts as badges: color, icon, and word together"
```

---

### Task 3: The Runs overview band

A clickable failure-signals line above the Runs tables.

**Amended 2026-07-28, after the tiles shipped and were seen.** This task originally added four boxed stat tiles (episodes, success rate as a hero figure, failures, models) above the signals. The user removed them on sight — "unnecessary and ugly" — because the numbers restate what the tables already show. The signal chips stay: they are light, and clicking one filters the runs table.

What that means for anyone reading this task now: build the `.signals` row and its click wiring, and skip every `.stats` / `.tile` / `.tile.hero` rule and the tile markup in `renderOverview`. `runStats` computes only what the chips consume — `malformed`, `blocked`, `errors`, `worst`. There is no hero figure on any view.

**Files:**
- Modify: `trajectory_viewer.html` — overview CSS; new `runStats()` and `renderOverview()` helpers; call from `renderRuns`
- Modify: `forge/tests/test_viewer.py`

**Interfaces:**
- Consumes: `badge()` from Task 2; the token set from Task 1
- Produces:
  - `runStats(eps) -> {total, passed, failed, rate, models, malformed, blocked, errors, worst}` where `eps` is the array of episode sessions, `models` is a sorted array of `{main, sub}` pair strings, and `worst` is `{scenario, passed, total}` or `null`
  - `renderOverview(content, stats)` — appends the stat row and signals line
  - Module-level `let issueFilter = null` — `null | "malformed" | "blocked" | "errors"`, read by the all-runs table filter in Task 5
  - CSS classes `.stats`, `.tile`, `.tile .lab`, `.tile .val`, `.tile .sub`, `.tile.hero`, `.signals`, `.signal`

- [ ] **Step 1: Write the failing test**

Append to `forge/tests/test_viewer.py`:

```python
def test_the_overview_computes_every_headline_number(viewer_html):
    stats = re.search(r"function runStats\(eps\) \{(.*?)\n\}", viewer_html, re.S)
    assert stats, "runStats() is missing"
    body = stats.group(1)
    for key in ("total", "passed", "failed", "rate", "models",
                "malformed", "blocked", "errors", "worst"):
        assert f"{key}:" in body or f"{key} =" in body, (
            f"runStats() does not compute {key}")


def test_exactly_one_hero_figure(viewer_css):
    """The dashboard leads with one number, not four competing ones."""
    hero = re.search(r"\.tile\.hero \.val \{(.*?)\}", viewer_css, re.S)
    assert hero, ".tile.hero .val rule is missing"
    size = re.search(r"font-size:\s*(\d+)px", hero.group(1))
    assert size and int(size.group(1)) >= 48, (
        "the hero figure is the one number a dashboard leads with: >=48px")


def test_signals_are_clickable_filters(viewer_html):
    assert "let issueFilter = null" in viewer_html
    assert 'data-issue=' in viewer_html


def test_stat_tiles_do_not_use_tabular_figures(viewer_css):
    """Tabular figures pad every digit to a zero's width -- loose at 48px."""
    tile = re.search(r"\.tile \.val \{(.*?)\}", viewer_css, re.S)
    assert tile, ".tile .val rule is missing"
    assert "tabular-nums" not in tile.group(1)
    assert "font-variant-numeric: normal" in tile.group(1), (
        "the body sets tabular-nums globally; tiles must opt out")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest forge/tests/test_viewer.py -v`

Expected: FAIL — `test_the_overview_computes_every_headline_number` fails with "runStats() is missing".

- [ ] **Step 3: Add the overview CSS**

Add to the stylesheet after the badge rules:

```css
  /* ---------- overview band: the first thing read ---------- */
  .stats {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(168px, 1fr));
    gap: 14px; margin: 20px 0 0;
  }
  .tile {
    background: var(--surface); border: 1px solid var(--hair);
    border-radius: 12px; box-shadow: var(--shadow); padding: 14px 16px 15px;
  }
  .tile .lab {
    font-size: 11.5px; font-weight: 600; color: var(--muted);
    letter-spacing: 0.02em; margin-bottom: 6px;
  }
  .tile .val {
    font-size: 30px; font-weight: 650; letter-spacing: -0.02em;
    line-height: 1.05; color: var(--ink);
    font-variant-numeric: normal;
  }
  .tile.hero .val { font-size: 52px; letter-spacing: -0.03em; }
  .tile .val.fail { color: var(--fail-ink); }
  .tile .val.models {
    font-size: 17px; font-weight: 600; line-height: 1.35;
    overflow-wrap: anywhere;
  }
  .tile .sub { margin-top: 7px; font-size: 12px; color: var(--ink-2); }

  .signals { display: flex; flex-wrap: wrap; gap: 9px; margin: 14px 0 0; }
  .signal {
    font: inherit; font-size: 12px; cursor: pointer;
    display: inline-flex; align-items: center; gap: 6px;
    padding: 4px 11px; border-radius: 999px;
    border: 1px solid var(--hair); background: var(--surface);
    color: var(--ink-2);
  }
  .signal .ic { font-size: 11px; line-height: 1; }
  .signal.warn { background: var(--warn-tint); color: var(--warn-ink);
                 border-color: transparent; }
  .signal.fail { background: var(--fail-tint); color: var(--fail-ink);
                 border-color: transparent; }
  .signal:hover { border-color: var(--ink-2); }
  .signal.on { outline: 2px solid var(--ink); outline-offset: 1px; }
```

- [ ] **Step 4: Add the state variable**

In the state block near the top of the script, beside `let sweepSel = 0;`, add:

```js
let issueFilter = null;    // null | "malformed" | "blocked" | "errors"
```

- [ ] **Step 5: Write `runStats` and `renderOverview`**

Add to the "shared pieces" section, after `countMalformed`:

```js
/* Every counter in one pass, so the tiles and the signals line can never
   disagree about what the same runs contain. */
/* A malformed line is a protocol fault and has its own counter; counting it
   here too would make the two signal chips overlap while reading as disjoint. */
function countErrors(d) {
  const faulted = s => s && s !== "ok" && s !== "malformed";
  let n = 0;
  for (const e of d.events || []) {
    if (e.type === "call" && faulted(e.status)) n++;
    if (e.type === "delegation")
      for (const c of e.calls || []) if (faulted(c.status)) n++;
  }
  return n;
}

function runStats(eps) {
  const total = eps.length;
  const passed = eps.filter(s => s.data.verdict && s.data.verdict.success).length;
  const failed = total - passed;
  const rate = total ? Math.round((passed / total) * 100) : 0;

  const models = [...new Set(eps.map(s =>
    s.data.main_model === s.data.sub_model
      ? String(s.data.main_model ?? "unknown")
      : `${s.data.main_model ?? "?"} / ${s.data.sub_model ?? "?"}`))].sort();

  let malformed = 0, blocked = 0, errors = 0;
  for (const s of eps) {
    malformed += countMalformed(s.data);
    blocked += s.data.blocked || 0;
    errors += countErrors(s.data);
  }

  /* The worst scenario is the one with the lowest pass rate; ties break to
     the one with more runs, so a single unlucky run does not top the list. */
  const byScenario = new Map();
  for (const s of eps) {
    const key = s.data.scenario_id;
    const seen = byScenario.get(key) || {scenario: key, passed: 0, total: 0};
    seen.total++;
    if (s.data.verdict && s.data.verdict.success) seen.passed++;
    byScenario.set(key, seen);
  }
  const worst = [...byScenario.values()].sort((a, b) =>
    (a.passed / a.total) - (b.passed / b.total) || b.total - a.total)[0] || null;

  return {total, passed, failed, rate, models, malformed, blocked, errors, worst};
}

function renderOverview(content, stats) {
  const configs = new Set();
  const band = document.createElement("div");
  band.innerHTML = `<div class="stats">
    <div class="tile">
      <div class="lab">Episodes</div>
      <div class="val">${stats.total}</div>
      <div class="sub">judged rollouts</div>
    </div>
    <div class="tile hero">
      <div class="lab">Success rate</div>
      <div class="val">${stats.rate}%</div>
      <div class="sub">${stats.passed} of ${stats.total} passed</div>
    </div>
    <div class="tile">
      <div class="lab">Failures</div>
      <div class="val${stats.failed ? " fail" : ""}">${stats.failed}</div>
      <div class="sub">${stats.failed ? "runs missed a gold write" : "none"}</div>
    </div>
    <div class="tile">
      <div class="lab">Models</div>
      <div class="val models">${stats.models.map(esc).join("<br>")}</div>
      <div class="sub">main agent and specialists</div>
    </div>
  </div>`;
  content.appendChild(band);

  /* Signals only appear when they have something to report: a row of zeros
     is noise that trains you to stop reading the row. */
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
  if (stats.worst && stats.worst.passed < stats.worst.total)
    signals.push({key: "worst", kind: "fail",
                  label: `worst scenario ${shortScenario(stats.worst.scenario)} — ${
                    stats.worst.passed}/${stats.worst.total} passed`});

  if (!signals.length) return;
  const row = document.createElement("div");
  row.className = "signals";
  row.innerHTML = signals.map(sig => `<button class="signal ${sig.kind}${
    issueFilter === sig.key ? " on" : ""}" data-issue="${esc(sig.key)}">
    <span class="ic" aria-hidden="true">${ICONS[sig.kind]}</span>${esc(sig.label)}</button>`).join("");
  row.querySelectorAll("[data-issue]").forEach(btn => {
    btn.onclick = () => {
      const key = btn.dataset.issue;
      if (key === "worst") {
        issueFilter = null;
        pendingQuery = shortScenario(stats.worst.scenario);
      } else {
        issueFilter = issueFilter === key ? null : key;
        pendingQuery = null;
      }
      render();
    };
  });
  content.appendChild(row);
}
```

- [ ] **Step 6: Add the `pendingQuery` state**

`renderOverview` sets `pendingQuery` so the "worst scenario" signal can pre-fill the table's search box. Beside `let issueFilter = null;` add:

```js
let pendingQuery = null;   // a search string the next runs-table render adopts
```

- [ ] **Step 7: Call the overview from `renderRuns`**

In `renderRuns`, replace the `content.insertAdjacentHTML("beforeend", ...)` block that writes the `<h2 class="sec">Runs</h2>` heading and the `.lede` sentence with:

```js
  content.insertAdjacentHTML("beforeend", `<h2 class="sec">Runs</h2>`);
  const stats = runStats(eps);
  renderOverview(content, stats);
```

Delete the now-unused `ok` and `softCount`… **keep `softCount`** — the Table 1 note still uses it. Delete only the `const ok = …` line and the `scenarios.length`-based lede sentence; `scenarios` itself is still used by the grid.

- [ ] **Step 8: Run the tests to verify they pass**

Run: `uv run pytest forge/tests/test_viewer.py -v`

Expected: PASS, 18 tests.

- [ ] **Step 9: Verify in the browser**

Open the file in Chrome on the Runs tab. Confirm against the real snapshot: **19** episodes, hero **11%**, **17** failures in red, models reading `gpt-5.6-sol`. The signals row shows the malformed and faulted-call counts and a worst-scenario chip. Click a signal — it takes the `on` outline (the table does not filter yet; Task 5 wires that). Toggle the theme and re-check.

- [ ] **Step 10: Commit**

```bash
git add trajectory_viewer.html forge/tests/test_viewer.py
git commit -m "Lead the Runs view with stat tiles and failure signals"
```

---

### Task 4: Restyle the verdict grid

The scenario × configuration matrix keeps its shape and gains a legend, losing the academic caption.

**Files:**
- Modify: `trajectory_viewer.html` — grid CSS; the Table 1 block inside `renderRuns`
- Modify: `forge/tests/test_viewer.py`

**Interfaces:**
- Consumes: `badge()`, `verdictBadge()` from Task 2
- Produces: CSS classes `.legend`, `.legend .key`, `.panel-title`; the grid's marks stay `a.xref[data-i]` so their click handler is unchanged

- [ ] **Step 1: Write the failing test**

Append to `forge/tests/test_viewer.py`:

```python
def test_academic_captions_are_gone(viewer_html):
    """No reader of a dashboard counts tables by number.

    Searches the hand-written source: a judge's rationale in the embedded
    snapshot can contain the words this test forbids.
    """
    source = viewer_source(viewer_html)
    assert not re.search(r"<b>Table \d+:</b>", source)
    assert 'class="tcap"' not in source


def test_the_grid_ships_a_legend(viewer_html):
    assert 'class="legend"' in viewer_html
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest forge/tests/test_viewer.py -v`

Expected: FAIL — `test_academic_captions_are_gone` fails; `<b>Table 1:</b>` is still in the file.

- [ ] **Step 3: Add the section and legend CSS**

Add to the stylesheet after the overview rules:

```css
  .panel-title {
    font-size: 14px; font-weight: 650; color: var(--ink);
    margin: 28px 0 9px; letter-spacing: -0.01em;
  }
  .panel-title .sub { font-weight: 400; color: var(--ink-2); font-size: 12.5px; }
  .legend {
    display: flex; flex-wrap: wrap; gap: 14px; align-items: center;
    margin: 0 0 10px; font-size: 12px; color: var(--ink-2);
  }
  .legend .key { display: inline-flex; align-items: center; gap: 5px; }
  .legend .dot {
    width: 9px; height: 9px; border-radius: 50%; display: inline-block;
  }
  .legend .dot.pass { background: var(--pass); }
  .legend .dot.fail { background: var(--fail); }
```

- [ ] **Step 4: Replace the Table 1 caption and note**

In `renderRuns`, in the `wrap.innerHTML` template, replace the leading `<p class="tcap">…</p>` with:

```js
    `<div class="panel-title">Verdicts by scenario and configuration
       <span class="sub">— every mark opens that run's transcript</span></div>
     <div class="legend">
       <span class="key"><span class="dot pass"></span>pass</span>
       <span class="key"><span class="dot fail"></span>fail</span>
       <span class="key">— not run</span>
     </div>
```

and replace the trailing `<p class="tnote">…</p>` with the same text under a new class:

```js
    `<p class="note">A verdict is the benchmark's own write-action check: the
      judge compares the agent's write calls against the scenario's gold
      writes, so a failure means a gold write was missing, its arguments were
      wrong, it was duplicated, or a later phase never unlocked — not that the
      harness errored.${softCount ? ` Runs tagged <i>soft judge</i> were scored
      by Gaia2's official soft judge (gpt-5.6-sol as checker); the rest use the
      deterministic scripted judge. Two marks in one cell are the same run
      under both judges.` : ""}</p>`
```

- [ ] **Step 4a: Annotate only the exception, never the rule**

Measured on the live snapshot before this step: the grid printed **264 "soft judge" tags across 314 badges** and a run label on nearly every cell — three lines per cell. That is the density this redesign exists to remove. An annotation carried by 84% of cells is not information.

The principle: *a per-cell annotation that is nearly universal carries no information. State it once, and annotate only what deviates.*

Tally the judges before building the grid, and break ties on name so the stated default never depends on the order runs happen to arrive in:

```js
  const judgeCounts = new Map();
  for (const s of eps) {
    const j = s.data.judge || "scripted";
    judgeCounts.set(j, (judgeCounts.get(j) || 0) + 1);
  }
  const majorityJudge = [...judgeCounts]
    .sort((a, b) => b[1] - a[1] || String(a[0]).localeCompare(String(b[0])))[0][0];
  const judgeLabel = j => j === "scripted" ? "scripted judge" : "soft judge";
```

Each mark then calls `badge()` **directly** rather than `verdictBadge()`, so the cell controls its own tagging — a tag only when the run departs from the majority, and a run label only where a cell holds more than one mark to tell apart:

```js
            const judge = s.data.judge || "scripted";
            const tag = judge !== majorityJudge
              ? `<span class="tag">${judgeLabel(judge)}</span>` : "";
            const lab = (runs.length > 1 && s.data.label)
              ? ` <span class="runlab">${esc(s.data.label)}</span>` : "";
```

The note then names the common case once. It must branch on which judge actually won — "official" belongs to Gaia2's soft judge and must never be glued to the deterministic scripted fallback:

```js
      Verdicts are scored by ${majorityJudge === "scripted"
        ? "the deterministic scripted judge"
        : "Gaia2's official soft judge (gpt-5.6-sol as checker)"} by default;
      a mark tagged with a different judge used that judge instead.
```

`softCount` is superseded by the tally — delete its declaration.

On the snapshot this was built against the judge split is `gpt-5.6-sol` 132 / `scripted` 25, so roughly **25** marks carry a tag and none reads "soft judge".

- [ ] **Step 5: Rename the `.tnote` rule**

The `.tnote` class is used in several places. Rename the CSS rule to `.note` and update every use:

```bash
sed -i '' 's/tnote/note/g' trajectory_viewer.html
grep -c 'class="note"' trajectory_viewer.html
```

Then delete the now-orphaned `.tcap` CSS rule.

- [ ] **Step 6: Give the grid's empty cells the dim class**

In the grid cell builder, the "not run" placeholder currently reads `<span style="color:var(--faint)">—</span>`; Task 1 changed it to `<span class="dim">—</span>`. Confirm it is there and that the run separator between two marks in one cell is also `<span class="dim"> · </span>`.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `uv run pytest forge/tests/test_viewer.py -v`

Expected: PASS, 21 tests.

- [ ] **Step 8: Verify in the browser**

The grid now sits under a plain title with a legend above it. Marks are badges. Clicking a mark still opens that run's transcript; Escape returns you to the same scroll position.

- [ ] **Step 9: Commit**

```bash
git add trajectory_viewer.html forge/tests/test_viewer.py
git commit -m "Give the verdict grid a legend instead of a table caption"
```

---

### Task 5: The all-runs table — models column and working signal filters

**Files:**
- Modify: `trajectory_viewer.html` — the Table 2 block inside `renderRuns`
- Modify: `forge/tests/test_viewer.py`

**Interfaces:**
- Consumes: `issueFilter` and `pendingQuery` from Task 3; `verdictBadge()` from Task 2
- Produces: rows carrying `data-issues` (a space-separated subset of `malformed blocked errors`) which the filter reads

- [ ] **Step 1: Write the failing test**

Append to `forge/tests/test_viewer.py`:

```python
def test_the_runs_table_shows_which_models_ran(viewer_html):
    """'What models ran this?' is a headline question, not a detail-page one."""
    assert "<th>models</th>" in viewer_html


def test_rows_carry_their_issues_for_the_signal_filter(viewer_html):
    assert "data-issues=" in viewer_html
    assert "issueFilter" in viewer_html
    assert "dataset.issues" in viewer_html
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest forge/tests/test_viewer.py -v`

Expected: FAIL — `test_the_runs_table_shows_which_models_ran` fails; there is no models column.

- [ ] **Step 3: Replace the table header**

In `renderRuns`, replace the `<thead>` row of the all-runs table with:

```js
  twrap.innerHTML = `<table class="tab"><thead><tr>
      <th>verdict</th><th>when</th><th>scenario</th><th>configuration</th>
      <th>ability</th><th>models</th>${hasLabels ? "<th>run</th>" : ""}
      <th>issues</th><th>answer</th><th class="n">wall&nbsp;s</th>
    </tr></thead><tbody>${
```

Note the reordering: verdict leads, and the `deleg`/`turns` counters are dropped from this table — they belong to the run detail, and their columns were pushing `answer` off the visible width. The models column replaces them.

- [ ] **Step 4: Replace the row builder**

Replace the `newestFirst.map(...)` row template with:

```js
    newestFirst.map(s => {
      const d = s.data, okr = !!(d.verdict && d.verdict.success);
      const mal = countMalformed(d), err = countErrors(d), blk = d.blocked || 0;
      const issues = [
        blk ? `${blk} blocked` : "",
        mal ? `${mal} malformed` : "",
        err ? `${err} faulted` : "",
      ].filter(Boolean).join(" · ");
      const tags = [mal ? "malformed" : "", blk ? "blocked" : "",
                    err ? "errors" : ""].filter(Boolean).join(" ");
      const models = d.main_model === d.sub_model
        ? esc(String(d.main_model ?? "—"))
        : `${esc(String(d.main_model ?? "?"))} <span class="dim">/</span> ${
            esc(String(d.sub_model ?? "?"))}`;
      return `<tr class="click" data-i="${sessions.indexOf(s)}" tabindex="0"
        data-verdict="${okr ? "ok" : "bad"}"
        data-ability="${esc(d.ability || "control")}"
        data-judge="${esc(d.judge || "scripted")}"
        data-issues="${tags}"
        data-text="${esc(JSON.stringify([d.scenario_id, d.config, d.ability,
                        d.judge, d.label, d.answer, d.main_model]).toLowerCase())}">
        <td>${verdictBadge(okr, d.judge)}</td>
        <td>${fmtWhen(d.started_at)}</td>
        <td>${esc(shortScenario(d.scenario_id))}</td>
        <td>${esc(d.config || "")}</td>
        <td>${esc(d.ability || "control")}</td>
        <td class="mono sm">${models}</td>${
        hasLabels ? `<td>${d.label ? esc(d.label) : "—"}</td>` : ""}
        <td>${issues ? `<span class="warn-text">${esc(issues)}</span>`
                     : `<span class="dim">clean</span>`}</td>
        <td title="${esc(d.answer ?? "")}">${esc(String(d.answer ?? "").slice(0, 44))}</td>
        <td class="n">${d.seconds ?? ""}</td></tr>`;
    }).join("")}</tbody></table>`;
```

- [ ] **Step 5: Add the two new cell classes**

Add to the stylesheet beside the `.dim` rule:

```css
  .warn-text { color: var(--warn-ink); }
  table.tab td.sm { font-size: 11.5px; color: var(--ink-2); }
```

- [ ] **Step 6: Teach the filter about issues and the pending query**

Replace the `apply` function and its wiring in `renderRuns` with:

```js
  if (pendingQuery) {
    $("input[type=search]", fbar).value = pendingQuery;
    pendingQuery = null;
  }
  const apply = () => {
    const q = $("input[type=search]", fbar).value.toLowerCase();
    const sel = {};
    for (const s of fbar.querySelectorAll("select")) sel[s.dataset.f] = s.value;
    let shown = 0;
    for (const tr of trs) {
      const hit = (!q || tr.dataset.text.includes(q))
        && (!sel.verdict || tr.dataset.verdict === sel.verdict)
        && (!sel.ability || tr.dataset.ability === sel.ability)
        && (!sel.judge || tr.dataset.judge === sel.judge)
        && (!issueFilter || tr.dataset.issues.split(" ").includes(issueFilter));
      tr.style.display = hit ? "" : "none";
      shown += hit;
    }
    $(".count", fbar).textContent =
      shown === trs.length ? `all ${trs.length} runs` : `${shown} of ${trs.length} runs`;
  };
```

- [ ] **Step 7: Replace the Table 2 caption**

Replace the `<p class="tcap"><b>Table 2:</b> …</p>` insertion with:

```js
  content.insertAdjacentHTML("beforeend",
    `<div class="panel-title">All runs
       <span class="sub">— newest first; click a row for its transcript</span></div>`);
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `uv run pytest forge/tests/test_viewer.py -v`

Expected: PASS, 23 tests.

- [ ] **Step 9: Verify in the browser**

Confirm the table leads with a badge, shows `gpt-5.6-sol` in a models column, and says `clean` where a run had no issues. Click the malformed signal in the overview — the table filters to just those runs and the count line updates; click it again to clear. Click the worst-scenario signal — the search box fills with the scenario id and the table narrows to it.

- [ ] **Step 10: Commit**

```bash
git add trajectory_viewer.html forge/tests/test_viewer.py
git commit -m "Surface models in the runs table and wire the signal filters"
```

---

### Task 6: Rebuild the transcript

The trajectory-clearness half of the request: a sticky run header, an extracted verdict panel, a timeline rail, and failed tool calls open by default.

**Preserve the shaping-signals feature.** `renderEpisode` carries work added separately (commit `d844695`) that this task must keep, restyled rather than removed. Two pieces:

1. A `${d.credit ? … }` block in the meta template reporting partial reward, coverage, exact-argument fidelity, and where the pivot landed.
2. A pivot-aware transcript loop that replaces the plain `cards` mapping:

```js
  const pivotAt = d.credit && d.credit.pivot != null ? d.credit.pivot : -1;
  const cards = (d.events || []).map((e, i) => {
    const node = turnNode(e);
    if (i === pivotAt) {
      node.classList.add("pivot");
      node.querySelector(".txt").insertAdjacentHTML("afterbegin",
        `<div class="pivotflag">▼ pivot — first fault (${esc(d.credit.pivot_kind)})</div>`);
    }
    return node;
  });
```

That loop is **not** yours to replace — leave it exactly as it stands. Step 6 rewrites the meta block around it, and Step 6a below re-homes the credit block into the new layout. Deleting either piece fails this task.

**Files:**
- Modify: `trajectory_viewer.html` — transcript CSS; `renderEpisode`, `turnNode`, `callHtml`; new `parseRationale`
- Modify: `forge/tests/test_viewer.py`

**Interfaces:**
- Consumes: `badge()`, `verdictBadge()`, `countMalformed()`, `countErrors()`
- Produces:
  - `parseRationale(text) -> {toolName: string|null, args: string[], attempts: string[], rest: string}` — pulls the missing gold write out of the judge's raw rationale
  - `turnStatus(event) -> "pass"|"fail"|"stage"|"plain"` — decides a turn's rail dot
  - CSS classes `.runbar`, `.runbar .facts`, `.verdict-panel`, `.verdict-panel.fail`, `.gold`, `.turn[data-status]`, `.call.bad`

- [ ] **Step 1: Write the failing test**

Append to `forge/tests/test_viewer.py`:

```python
def test_the_run_header_sticks(viewer_css):
    """Scroll 200 turns down and you still know which run you are reading."""
    bar = re.search(r"\.runbar \{(.*?)\}", viewer_css, re.S)
    assert bar, ".runbar rule is missing"
    assert "position: sticky" in bar.group(1)


def test_the_judges_rationale_is_parsed_not_dumped(viewer_html):
    fn = re.search(r"function parseRationale\(text\) \{(.*?)\n\}",
                   viewer_html, re.S)
    assert fn, "parseRationale() is missing"
    body = fn.group(1)
    assert "tool name:" in body, "the missing gold write must be extracted"
    assert "List of matching attempts" in body, (
        "the attempt dump must be separated from the headline")


def test_failed_tool_calls_open_by_default(viewer_html):
    """The evidence for a failure should not be behind a click."""
    assert 'bad ? " open" : ""' in viewer_html, (
        "delegation call lists must render <details open> when a call faulted")
    assert 'class="call bad"' in viewer_html, (
        "a faulted call must be marked so its rail turns red")


def test_the_transcript_has_a_status_rail(viewer_css, viewer_html):
    assert re.search(r"\.turn\[data-status=\"fail\"\]::before", viewer_css), (
        "each turn needs a rail dot colored by its status")
    assert "function turnStatus(e)" in viewer_html


def test_the_shaping_signals_feature_survived_the_rebuild(viewer_html):
    """Partial reward and the pivot marker predate this redesign (d844695).

    The transcript rebuild restyles them; it does not get to drop them.
    """
    assert "d.credit" in viewer_html, "the shaping-signals block is gone"
    assert "pivotAt" in viewer_html, "the pivot-marking loop is gone"
    assert "pivotflag" in viewer_html, "the pivot flag is gone"
    assert 'classList.add("pivot")' in viewer_html
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest forge/tests/test_viewer.py -v`

Expected: FAIL — `test_the_run_header_sticks` fails with ".runbar rule is missing".

- [ ] **Step 3: Replace the transcript CSS**

Replace the whole `/* ---------- transcript: dialogue with margin speakers ---------- */` block (through the `pre.blk` rule) with:

```css
  /* ---------- run header: pinned so context never scrolls away ---------- */
  .runbar {
    position: sticky; top: 0; z-index: 5;
    background: var(--plane); border-bottom: 1px solid var(--hair);
    padding: 12px 0 11px; margin-bottom: 4px;
  }
  .runbar h3 {
    margin: 0; font-size: 16px; font-weight: 650; letter-spacing: -0.01em;
    display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  }
  .runbar .facts {
    margin-top: 7px; font-size: 12px; color: var(--ink-2);
    display: flex; flex-wrap: wrap; gap: 4px 16px;
  }
  .runbar .facts b { color: var(--ink); font-weight: 600; }

  /* ---------- the verdict, read before the transcript ---------- */
  .verdict-panel {
    margin: 16px 0 0; padding: 13px 16px; border-radius: 10px;
    background: var(--wash); border: 1px solid var(--hair);
    font-size: 13px; color: var(--ink-2);
  }
  .verdict-panel.fail { background: var(--fail-tint); border-color: transparent; }
  .verdict-panel .head {
    font-weight: 650; color: var(--ink); font-size: 13.5px; margin-bottom: 7px;
  }
  .verdict-panel .gold {
    margin: 8px 0 0; padding: 9px 12px; border-radius: 8px;
    background: var(--surface); border: 1px solid var(--hair);
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 11.5px; color: var(--ink); white-space: pre-wrap;
    overflow-wrap: anywhere;
  }
  .verdict-panel details { margin-top: 9px; }
  .verdict-panel summary {
    cursor: pointer; font-size: 12px; color: var(--ink-2); width: fit-content;
  }
  .verdict-panel pre {
    margin: 7px 0 0; font-size: 11px; line-height: 1.45; max-height: 260px;
    overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere;
    color: var(--ink-2);
  }

  /* ---------- transcript: a timeline with a status rail ---------- */
  .transcript { margin-top: 20px; }
  .turn {
    position: relative;
    display: grid; grid-template-columns: 118px minmax(0, 1fr); gap: 0 26px;
    padding: 10px 0;
  }
  /* the rail runs through the gutter between the speaker and the matter */
  .turn::after {
    content: ""; position: absolute; left: 130px; top: 0; bottom: 0;
    width: 2px; background: var(--grid);
  }
  .turn:first-child::after { top: 15px; }
  .turn:last-child::after { bottom: auto; height: 15px; }
  .turn::before {
    content: ""; position: absolute; left: 126px; top: 13px; z-index: 1;
    width: 10px; height: 10px; border-radius: 50%;
    background: var(--axis); border: 2px solid var(--plane);
  }
  .turn[data-status="pass"]::before { background: var(--pass); }
  .turn[data-status="fail"]::before { background: var(--fail); }
  .turn[data-status="stage"]::before { background: var(--grid); }
  @media (max-width: 720px) {
    .turn { grid-template-columns: 84px minmax(0, 1fr); gap: 0 20px; }
    .turn::after { left: 92px; }
    .turn::before { left: 88px; }
  }
  .turn .spk {
    color: var(--ink-2); font-size: 11.5px; font-weight: 600;
    text-align: right; padding-top: 2px;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  .turn .spk .t {
    display: block; font-weight: 400; font-size: 10.5px; color: var(--muted);
  }
  .turn .txt { white-space: pre-wrap; overflow-wrap: anywhere; font-size: 13px; }
  .turn.stage .txt { color: var(--muted); }
  .turn.fail .spk { color: var(--fail-ink); }
  /* the pivot is the first faulting event: frozen prefix above it, the
     trainable suffix from it down. It marks a boundary, so it gets a rule
     across the turn rather than another dot on the rail. */
  .turn.pivot { border-top: 2px solid var(--fail); }
  .pivotflag {
    color: var(--fail-ink); font-size: 11px; font-weight: 600;
    margin-bottom: 3px;
  }
  .turn .report { margin-top: 6px; color: var(--ink-2); }
  .turn .report b { color: var(--ink); font-weight: 600; }

  details.calls { margin-top: 7px; }
  details.calls summary {
    cursor: pointer; font-size: 11.5px; color: var(--ink-2); width: fit-content;
  }
  .call {
    padding: 7px 0 3px 10px; margin-top: 5px;
    border-left: 2px solid var(--grid);
  }
  .call.bad { border-left-color: var(--fail); }
  .call .sig { font-size: 11.5px; overflow-wrap: anywhere; color: var(--ink); }
  .call .flag { color: var(--fail-ink); font-size: 11.5px; font-weight: 600; }
  .call pre {
    margin: 5px 0; padding: 8px 11px;
    background: var(--wash); border-radius: 8px;
    max-height: 240px; overflow: auto;
    font-size: 11px; line-height: 1.45;
    white-space: pre-wrap; overflow-wrap: anywhere; color: var(--ink-2);
  }
  pre.blk {
    background: var(--wash); border-radius: 8px; padding: 9px 12px; margin: 8px 0;
    overflow: auto; max-height: 70vh; font-size: 11.5px; line-height: 1.45;
    white-space: pre-wrap; overflow-wrap: anywhere;
  }
```

- [ ] **Step 4: Write `parseRationale`**

Add to the shared-pieces section:

```js
/* The scripted judge reports a failure as a wall of text: a headline, the
   oracle call it wanted, its arguments, then every attempt it tried to match.
   Only the first three lines answer "what went wrong", so they get pulled to
   the front and the attempt log goes behind a disclosure. */
function parseRationale(text) {
  const raw = String(text || "");
  const toolName = (raw.match(/tool name:\s*(\S+)/) || [])[1] || null;

  const args = [];
  const argBlock = raw.split(/tool args:\s*/)[1];
  if (argBlock) {
    for (const line of argBlock.split("\n")) {
      if (!line.startsWith("-")) break;
      args.push(line.slice(1).trim());
    }
  }

  const [before, after] = raw.split("List of matching attempts:");
  const attempts = after
    ? after.split("\n").map(l => l.replace(/^-/, "").trim()).filter(Boolean)
    : [];

  return {toolName, args, attempts, rest: (before || raw).trim()};
}
```

- [ ] **Step 5: Write `turnStatus`**

Add beside `turnNode`:

```js
/* The rail's dot answers "where did this go wrong" without reading a word. */
function turnStatus(e) {
  if (e.type === "surrender" || e.type === "stop") return "fail";
  if (e.type === "done") return "pass";
  if (e.type === "wait" || e.type === "notification") return "stage";
  if (e.type === "call" && e.status && e.status !== "ok") return "fail";
  if (e.type === "delegation"
      && (e.calls || []).some(c => c.status && c.status !== "ok")) return "fail";
  return "plain";
}
```

- [ ] **Step 6: Rewrite the head of `renderEpisode`**

Replace the `const meta = document.createElement("div"); meta.innerHTML = …` block (everything from `const meta` through `content.appendChild(meta);`) with:

```js
  const bar = document.createElement("div");
  bar.className = "runbar";
  bar.innerHTML = `
    <h3>${verdictBadge(okr, d.judge)}
      <span>${esc(shortScenario(d.scenario_id || s.name))}</span>
      <span class="dim">·</span>
      <span>${esc(d.config || "?")}</span>${
      d.label ? ` <span class="tag">${esc(d.label)}</span>` : ""}</h3>
    <div class="facts">
      <span>ability <b>${esc(d.ability || "control")}</b></span>
      <span>models <b>${esc(d.main_model || "?")}</b>${
        d.sub_model && d.sub_model !== d.main_model
          ? ` / <b>${esc(d.sub_model)}</b>` : ""}</span>
      <span><b>${d.delegations ?? 0}</b> delegations</span>
      <span><b>${d.specialist_turns ?? 0}</b> specialist turns</span>
      <span><b>${d.seconds ?? "—"}</b> s</span>
      <span>judge <b>${esc(judge)}</b></span>
      ${mal ? `<span class="warn-text">${mal} malformed</span>` : ""}
      ${d.blocked ? `<span class="warn-text">${d.blocked} blocked</span>` : ""}
    </div>`;
  content.appendChild(bar);

  const parsed = parseRationale(d.verdict && d.verdict.rationale);
  const panel = document.createElement("div");
  panel.className = "verdict-panel" + (okr ? "" : " fail");
  if (okr) {
    panel.innerHTML = `<div class="head">Passed</div>
      <div>The agent's write calls matched the scenario's gold writes.${
        d.answer != null ? ` Final answer: <b>${esc(d.answer)}</b>.` : ""}</div>`;
  } else if (parsed.toolName) {
    panel.innerHTML = `<div class="head">Missing gold write</div>
      <div>The judge expected this call and did not find a match:</div>
      <div class="gold">${esc(parsed.toolName)}${
        parsed.args.length ? "\n  " + parsed.args.map(esc).join("\n  ") : ""}</div>${
      parsed.attempts.length
        ? `<details><summary>${parsed.attempts.length} matching attempt${
            parsed.attempts.length === 1 ? "" : "s"} the judge tried</summary>
           <pre>${esc(parsed.attempts.join("\n"))}</pre></details>` : ""}${
      d.answer != null
        ? `<div style="margin-top:9px">Final answer: <b>${esc(d.answer)}</b>.</div>` : ""}`;
  } else {
    panel.innerHTML = `<div class="head">Failed</div>
      <div>${parsed.rest
        ? esc(parsed.rest.slice(0, 1200))
        : `The judge reports no rationale. A failure means the agent's write
           calls did not match the scenario's gold writes exactly — a write
           missing, its arguments off, or a later phase never unlocked. The
           tool calls below are the evidence.`}</div>${
      d.answer != null
        ? `<div style="margin-top:9px">Final answer: <b>${esc(d.answer)}</b>.</div>` : ""}`;
  }
  content.appendChild(panel);

  if ((d.blocked_reasons || []).length)
    content.insertAdjacentHTML("beforeend",
      `<p class="note">Blocked: ${esc(d.blocked_reasons.join(" · "))}</p>`);
  content.insertAdjacentHTML("beforeend", `<p class="path">${esc(s.path)}</p>`);
```

- [ ] **Step 6a: Re-home the shaping-signals block**

The old meta template you just replaced contained a `${d.credit ? … }` block. It does not disappear — it becomes its own element after the verdict panel. Append this immediately after the `content.appendChild(panel);` line:

```js
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
```

and add its rule to the stylesheet beside the verdict-panel rules:

```css
  .credit {
    display: flex; flex-wrap: wrap; gap: 5px 18px; align-items: baseline;
    margin: 11px 0 0; font-size: 12px; color: var(--ink-2);
  }
  .credit .lab {
    font-size: 11px; font-weight: 600; color: var(--muted);
    letter-spacing: 0.02em;
  }
  .credit b { color: var(--ink); font-weight: 650; }
```

- [ ] **Step 7: Set the rail status on each turn**

In `turnNode`, just before the closing `return div;`, add:

```js
  div.dataset.status = turnStatus(e);
```

- [ ] **Step 8: Open faulted call lists by default**

In `turnNode`'s delegation branch, replace the `<details class="calls">` opening tag with one that opens when something faulted:

```js
        ? `<details class="calls"${bad ? " open" : ""}><summary>${calls.length} tool call${
            calls.length > 1 ? "s" : ""}${bad ? ` <span class="flag">${bad} faulted</span>` : ""
          }</summary>${calls.map(callHtml).join("")}</details>`
```

- [ ] **Step 9: Mark the faulted calls themselves**

Replace `callHtml` with:

```js
function callHtml(c) {
  const bad = c.status && c.status !== "ok";
  if (c.status === "malformed" || c.status === "false-outage") {
    const label = c.status === "malformed" ? "unparseable line"
      : "rejected false outage claim";
    return `<div class="call bad"><span class="flag">${label}</span>
      <div class="sig">${esc(String(c.raw ?? c.result ?? "").slice(0, 400))}</div></div>`;
  }
  const flag = bad ? ` <span class="flag">${esc(c.status)}</span>` : "";
  return `<div class="call${bad ? " bad" : ""}">
    <div class="sig">${esc(c.tool)}(${esc(JSON.stringify(c.args))})${flag}</div>
    <pre>${esc(c.result ?? "")}</pre></div>`;
}
```

- [ ] **Step 10: Run the tests to verify they pass**

Run: `uv run pytest forge/tests/test_viewer.py -v`

Expected: PASS, 28 tests.

- [ ] **Step 11: Verify in the browser**

Open a failing run — for example the `28_znpabl` / `open-docs-binf` episode, whose rationale names `Calendar__add_calendar_event`. Confirm: the header stays pinned while you scroll; the verdict panel reads "Missing gold write" with that tool name and its arguments in a monospace block, and the matching-attempt dump sits behind a disclosure; the rail runs down the transcript with red dots on the faulted turns; a delegation whose calls faulted is already expanded. Check a passing run and the theme toggle too.

- [ ] **Step 12: Commit**

```bash
git add trajectory_viewer.html forge/tests/test_viewer.py
git commit -m "Rebuild the transcript as a timeline with an extracted verdict"
```

---

### Task 7: The remaining views

Shipped-task runs, evidence files, the empty state, and the page header — everything that still wears the old costume.

**Files:**
- Modify: `trajectory_viewer.html` — `renderBreakdowns`, `renderBreakdownDetail`, `renderSweeps`, the empty state in `render()`, the `<header>` markup and its CSS
- Modify: `forge/tests/test_viewer.py`

**Interfaces:**
- Consumes: `badge()`, `verdictBadge()`, `.panel-title`, `.note`, `.tile` from earlier tasks
- Produces: nothing new — this task is the sweep that leaves no view in the old style

- [ ] **Step 1: Write the failing test**

Append to `forge/tests/test_viewer.py`:

```python
def test_no_view_still_wears_the_paper_costume(viewer_html):
    """One surface, one design: no leftovers from the evidence-page era.

    Searches the hand-written source: "Table 3:" and its kin can occur inside
    a run's transcript text, which lives in the embedded snapshot.
    """
    source = viewer_source(viewer_html)
    for relic in ('class="draftline"', 'class="colophon"', "Table 3:", "Table 4:"):
        assert relic not in source, f"{relic} survived the redesign"


def test_no_stat_tiles_anywhere(viewer_css):
    """The boxed summary band was removed on 2026-07-28; keep it removed."""
    for gone in (".stats", ".tile", ".tile.hero"):
        assert gone + " {" not in viewer_css, f"{gone} came back"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest forge/tests/test_viewer.py -v`

Expected: FAIL — `class="draftline"` is still in the header markup.

- [ ] **Step 3: Rebuild the page header**

Replace the `<header>…</header>` block in the body with:

```html
  <header>
    <div class="titlerow">
      <h1>Run dashboard</h1>
      <div class="acts">
        <label for="pick" tabindex="0" role="button">open files</label>
        <input id="pick" type="file" accept=".json,application/json" multiple>
        <button id="theme">theme</button>
      </div>
    </div>
    <p class="source" id="draftline">multi-agent-rl-datagen — no data loaded</p>
  </header>
```

The element keeps the id `draftline` so the existing `$("#draftline")` write in `render()` still works; only its class changes.

Replace the header CSS block (`header h1` through `input[type="file"]`) with:

```css
  header .titlerow {
    display: flex; align-items: baseline; justify-content: space-between;
    gap: 16px; flex-wrap: wrap;
  }
  header h1 {
    font-size: 22px; font-weight: 650; letter-spacing: -0.02em;
    margin: 0; line-height: 1.2;
  }
  header .acts { display: flex; gap: 8px; }
  header .acts button, header .acts label {
    font: inherit; font-size: 12.5px; color: var(--ink-2);
    background: var(--surface); border: 1px solid var(--hair);
    border-radius: 8px; padding: 4px 12px; cursor: pointer;
  }
  header .acts button:hover, header .acts label:hover {
    border-color: var(--ink-2); color: var(--ink);
  }
  header .source { color: var(--muted); font-size: 12px; margin: 6px 0 0; }
  input[type="file"] { display: none; }
```

Also change the page background: in the `body` rule, `background: var(--paper)` became `var(--plane)` in Task 1 — confirm it reads `var(--plane)`.

- [ ] **Step 4: Give the shipped-task view a summary line**

**Amended 2026-07-28:** this step originally added a row of stat tiles here. Tiles were removed from the product — the user called the boxed summary band unnecessary and ugly — so this step now writes a one-line summary in prose instead. Do not add tiles, cards, or a display-size figure.

Replace the `content.insertAdjacentHTML("beforeend", …)` heading block in `renderBreakdowns` with:

```js
  const bok = bds.filter(s => s.data.success).length;
  const partials = bds.map(s => s.data.partial).filter(v => typeof v === "number");
  const meanPartial = partials.length
    ? (partials.reduce((a, b) => a + b, 0) / partials.length).toFixed(2) : null;
  content.insertAdjacentHTML("beforeend",
    `<h2 class="sec">Shipped-task runs</h2>
     <p class="lede"><b>${bds.length}</b> containerized AppWorld episodes from
     <span class="mono">jobs/</span> — ${bok} passed,
     <span class="${bds.length - bok ? "warn-text" : ""}">${bds.length - bok}
     failed</span>, scored by AppWorld's own per-requirement check${
     meanPartial ? `, mean partial credit <b>${meanPartial}</b>` : ""}.</p>
     <div class="panel-title">Verifier results
       <span class="sub">— by campaign and trial; click a row for its ledger</span></div>`);
```

- [ ] **Step 5: Restyle the evidence-files view**

In `renderSweeps`, replace the `<p class="tcap"><b>Table 4:</b> …</p>` insertion with:

```js
  content.insertAdjacentHTML("beforeend",
    `<div class="panel-title">${esc(s.name)}
       <span class="sub">— ${esc(s.path)}</span></div>${
     note ? `<p class="note">${esc(note)}</p>` : ""}`);
```

and change its `.lede` sentence to drop the "Column heads sort; the blank restricts" instruction, which described the retired form-blank inputs:

```js
     `<p class="lede">The repository's measurement evidence from
     <span class="mono">sweep/</span> — one summary file per claim. Click a
     column head to sort.</p>`
```

- [ ] **Step 6: Restyle the empty state**

In `render()`, replace the no-sessions `content.innerHTML` with:

```js
    content.innerHTML = `<div class="abstract">
      <h2>No runs loaded</h2>
      <p>This page carries its own data — a snapshot of the repository's logs
      is embedded in the file — and this copy's snapshot is empty. Refresh it
      with <code>uv run python -m scripts.embed_logs</code>, or drop trajectory
      JSON files anywhere on this page.</p></div>`;
```

- [ ] **Step 7: Fix the `renderBreakdownDetail` header**

Replace its `<h3 class="subsec">` line with a run bar matching Task 6's:

```js
  const bar = document.createElement("div");
  bar.className = "runbar";
  bar.innerHTML = `<h3>${verdictBadge(!!d.success)}
      <span>${esc(breakdownLabel(s))}</span></h3>
    <div class="facts">
      <span>partial <b>${d.partial ?? "—"}</b></span>${
      d.passes != null ? `<span><b>${d.passes}</b> requirements passed</span>
        <span><b>${d.failures ?? "?"}</b> failed</span>` : ""}
      <span><b>${d.delegations ?? d.ledger.length}</b> delegations</span>
      <span><b>${d.ledger.reduce((n, l) => n + (l.specialist_turns || 0), 0)}</b>
        specialist turns</span>
    </div>`;
  content.appendChild(bar);
  content.insertAdjacentHTML("beforeend", `<p class="path">${esc(s.path)}</p>`);
```

Delete the old `meta` div construction in that function, but keep the failed-requirements `<details>` block, appending it after the path line.

- [ ] **Step 8: Delete the orphaned CSS**

Remove `.subsec` if nothing references it any more, and remove the `.rationale` rule (replaced by `.verdict-panel`). Confirm:

```bash
grep -n "subsec\|rationale\|tcap\|dag\b" trajectory_viewer.html
```

Expected: no output.

- [ ] **Step 9: Run the tests to verify they pass**

Run: `uv run pytest forge/tests/test_viewer.py -v`

Expected: PASS, 30 tests.

- [ ] **Step 10: Verify in the browser**

Visit all three tabs in both themes. Every view leads with a plain title; no captions, no dagger, no draft line. The Shipped-task tab shows its own four tiles.

- [ ] **Step 11: Commit**

```bash
git add trajectory_viewer.html forge/tests/test_viewer.py
git commit -m "Bring the remaining views onto the dashboard system"
```

---

### Task 8: Rewrite DESIGN.md and verify the whole surface

`DESIGN.md` currently documents the opposite of what the file now is — it forbids cards, tiles, badges, and color. It is replaced, and the redesign gets its final review.

**Files:**
- Modify: `DESIGN.md` (full rewrite)
- Modify: `forge/tests/test_viewer.py`

**Interfaces:**
- Consumes: the finished viewer
- Produces: nothing downstream

- [ ] **Step 1: Write the failing test**

Append to `forge/tests/test_viewer.py`:

```python
_DESIGN = _ROOT / "DESIGN.md"


def test_design_doc_describes_the_shipped_palette():
    """A design doc that contradicts the artifact is worse than none."""
    text = _DESIGN.read_text()
    for token in ("#0ca30c", "#d03b3b", "#fab219"):
        assert token in text, f"DESIGN.md never mentions {token}"
    assert "signal red" not in text.lower(), (
        "the one-accent rule was overturned on 2026-07-28")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest forge/tests/test_viewer.py -v`

Expected: FAIL — DESIGN.md still describes the signal-red system.

- [ ] **Step 3: Rewrite DESIGN.md**

Replace the file entirely. Keep the YAML frontmatter shape (`name`, `description`, `colors`, `typography`, `spacing`, `components`) but fill it with the shipped values from Task 1's token block. The prose sections to write, in order:

- **Overview** — the north star is now "a dashboard you read at a glance". State plainly that the previous direction (the proceedings/evidence page, its no-chrome refusal, and its single-accent rule) was **overturned by the user on 2026-07-28** because it read as a costume, its text was too dense, and key run information was not findable at once. Record the three-option choice that was made (overview + tables, over a run-card grid and a master-detail split).
- **Colors** — the token table for both modes; the three status roles and their mark/ink/tint split; the rule that a status color always ships with an icon and a word; the note that light-mode `--warn` is a documented sub-3:1 exception and that `--muted` is for de-emphasized labels only.
- **Typography** — the system sans throughout; `tabular-nums` in table columns only, proportional figures in tiles and the hero; monospace confined to model names, tool signatures, paths, and code.
- **Layout** — 1080px column; the Runs view's order (title, source line, tabs, stat row, signals, verdict grid, all-runs table); the sticky run bar in detail views.
- **Components** — stat tile, hero figure, signal chip, status badge, table, verdict panel, transcript turn with its status rail.
- **Do's and Don'ts** — replace the old refusals. Do: one hero per view; three channels on every status; both themes for every token; keep the file self-contained. Don't: paint a status by color alone; invent a shade outside the documented palette without re-running the contrast test; put `tabular-nums` on a display figure; add a second hero figure to one view.

Delete every mention of the retired system: signal red, hairline table grammar as *the* structure, the no-chrome rule, the confined-monospace rule as written, the bold-figure rule, "Table N" captions, and daggers.

- [ ] **Step 4: Run the whole test suite**

Run: `uv run pytest forge/tests/test_viewer.py -v`

Expected: PASS, 31 tests.

Then confirm nothing else in the repo broke:

Run: `uv run pytest -q`

Expected: the suite's usual result, with no new failures attributable to this branch.

- [ ] **Step 5: Refresh the snapshot and confirm the rewriter still works**

Run: `uv run python -m scripts.embed_logs`

Expected: `embedded 64 log files (… kB) into trajectory_viewer.html`. If it raises "the viewer and this script have drifted", the snapshot block was damaged — restore it before continuing.

- [ ] **Step 6: Final visual review**

Open the file in Chrome and walk every surface in **both** themes: Runs (tiles, signals, grid, table), a failing run's transcript, a passing run's transcript, Shipped-task runs and one of its ledgers, Evidence files, and the empty state (test it by temporarily loading the page with the snapshot block emptied, or trust the code path). Look specifically for: label collisions in the stat row at narrow widths, the sticky bar overlapping content, table overflow, and any text that lost contrast in one theme.

Fix anything you find before committing, then re-run `uv run pytest forge/tests/test_viewer.py -v`.

- [ ] **Step 7: Commit**

```bash
git add DESIGN.md forge/tests/test_viewer.py trajectory_viewer.html
git commit -m "Document the dashboard system; retire the evidence-page design"
```

---

## Self-Review

**Spec coverage.** Every spec section maps to a task: the palette and both themes → Task 1; badges → Task 2; the overview band with totals, success rate, failures, models, and clickable failure signals → Task 3; verdict grid → Task 4; the runs table's models column and signal filtering → Task 5; the transcript's sticky header, extracted verdict panel, typed events, pre-expanded failed calls, and timeline rail → Task 6; the shipped-task and evidence views, empty state, and header → Task 7; the DESIGN.md rewrite and the "missing fields render as —" / snapshot-integrity checks → Task 8. The spec's non-goals are respected: no data-pipeline change, no new loading model.

**Known gaps, stated rather than hidden.** Two spec details are handled by convention rather than by a dedicated step: "large snapshots keep the chunked row rendering" (`batchAppend` is never touched, so it survives) and "reduced motion" (the existing `prefers-reduced-motion` guard on `#content` is never touched, and no task adds an animation). The spec's line about `scripts/validate_palette.js` cannot be honored on this machine — Node.js is not installed — so Task 1's Python contrast tests stand in for it, and the plan forbids inventing shades outside the documented palette.

**Type consistency.** `verdictBadge(ok, judge)` and `badge(kind, label)` are defined in Task 2 and used with those exact signatures in Tasks 3–7. `runStats(eps)` returns the nine keys Task 3's test asserts and Task 5 reads. `countErrors(d)` is defined in Task 3 and reused in Tasks 5 and 6. `issueFilter` and `pendingQuery` are declared in Task 3 and consumed in Task 5. `parseRationale(text)` and `turnStatus(e)` are defined and used within Task 6. The `.note` class replaces `.tnote` in Task 4 and is used by Tasks 6 and 7.
