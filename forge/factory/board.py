"""The factory board: the whole queue, at a glance, from one file.

The loading model is the repo's committed one -- the snapshot. The viewer once
had a live File System Access connection and it was deliberately retired in
f3c66bc ("Opening the file is the whole workflow again, with no permission
prompt in front of it"), so the board embeds its data and reloads itself
rather than asking for a folder. The orchestrator re-renders after every
transition; the page's own timer picks that up.

What the board must never do: assert that an action succeeded. It renders
state and the command that would change it. The next render shows what
actually happened -- which is also why the generated timestamp is always on
screen, so a stopped orchestrator reads as stale instead of as calm.
"""

from __future__ import annotations

import html
import json

from forge.factory.state import LAST_STAGE, JobState

#: The stage states the grid can show, and the legend word for each. `pending`
#: covers both "not started" and "never reached": the legend names it
#: "— not run" so an unreached stage is an explicit absence, never a blank
#: that a reader could mistake for a pass.
STAGE_STATES = {
    "passed": "gate-passed",
    "running": "running",
    "failed": "gate-failed",
    "parked": "parked for a human",
    "pending": "— not run",
}

#: Statuses that mean a human is the next actor, and the CLI verb that unblocks
#: each. Rendered verbatim beside the job; the board runs nothing itself.
HUMAN_GATES = {
    "awaiting-spec-approval": "approve {job} --spec",
    "awaiting-release-review": "approve {job} --release",
    "stuck": "status {job}",
}


def stage_cell(state: JobState, stage: int) -> str:
    """What the grid shows for one (job, stage) cell.

    Reads the attempts, never the cursor alone: a stage the cursor has passed
    but that has no recorded attempt is still `pending`, because borrowing the
    neighbouring stage's state would draw a pass that never happened.
    """
    attempts = [a for a in state.attempts if a.stage == stage]
    if not attempts:
        return "pending"
    latest = attempts[-1]
    if latest.ended is None:
        return "running"
    if latest.outcome == "gate-failed":
        return "failed"
    if latest.outcome == "gate-passed":
        if state.stage == stage and state.status.startswith("awaiting-"):
            return "parked"
        return "passed"
    return "failed"


def _job_row(state: JobState) -> dict:
    """One row's data, already decided -- the template only formats it.

    Two fields go beyond the bare cell verdict: `cap` and `attempt_counts`.
    A gate that has failed once carries no more information than the badge
    already shows, but a gate on its second or third attempt is closing in on
    `caps.attempts_per_stage`, after which the job parks `stuck` -- and that
    is exactly the moment a reader most needs "attempt 2 of 3" spelled out
    beside the mark, not just a bare fail.

    `attempt_counts` reads the `attempt` field, not the length of the
    attempts list: a stage that a reviewer and an author both touched within
    the same attempt cycle (two `Attempt` records, both `attempt: 1`) is
    still one attempt, not two, and only the highest `attempt` number seen
    says how close the stage is to its cap.
    """
    return {
        "job": state.job,
        "status": state.status,
        "stage": state.stage,
        "updated": state.updated,
        "spend": state.spend.total_tokens,
        "budget": state.caps.total_tokens,
        "cells": [stage_cell(state, n) for n in range(1, LAST_STAGE + 1)],
        "cap": state.caps.attempts_per_stage,
        "attempt_counts": [
            max((a.attempt for a in state.attempts if a.stage == n), default=0)
            for n in range(1, LAST_STAGE + 1)
        ],
        "command": (
            "python -m forge.factory.cli "
            + HUMAN_GATES[state.status].format(job=state.job)
            if state.status in HUMAN_GATES else None
        ),
    }


def render_board(states: list[JobState], *, generated: str,
                 refresh_seconds: int = 5) -> str:
    """The complete page. `generated` is rendered, always, so staleness shows."""
    rows = [_job_row(s) for s in states]
    data = json.dumps({"generated": generated, "rows": rows}, indent=1)
    # The implementer writes _TEMPLATE below: a full <!doctype html> document
    # carrying the committed tokens in all three theme scopes, the badge()
    # builder, the legend, the grid panel, and the refresh timer.
    return _TEMPLATE.format(
        data=html.escape(data, quote=False),
        refresh_seconds=refresh_seconds,
        generated=html.escape(generated),
    )


_TEMPLATE = """\
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Factory board — rl-datagen</title>
<!--
THESIS: the whole job queue, at a glance, from one file. Every status ships
as color + icon + word at once through one badge() builder, so the queue
reads before any prose does and survives color-blindness, grayscale, and
forced-colors.
LOADING MODEL: the repo's committed one. This page carries its data -- a
JSON snapshot sits in the #board-data block below, the same technique
trajectory_viewer.html uses for its own #embedded-logs snapshot. The
viewer once also held a live File System Access folder connection with a
remembered directory handle; that was deliberately retired in commit
f3c66bc ("Opening the file is the whole workflow again, with no permission
prompt in front of it"), and this board does not revive it for itself --
no folder connection, no write capability, no server call, no external
reference of any kind. The orchestrator re-renders the file after every
transition; this page's own timer reloads it on an interval, with a pause
control for a reader who is mid-read.
WHAT THIS PAGE NEVER DOES: assert that an action succeeded. Every row that
needs a human shows the exact command a human would run, as text to copy --
the page never claims that command's outcome, whatever it would be. The next
reload shows what actually happened, which is also why the generated
timestamp is always on screen: a stopped orchestrator must read as stale,
never as calm.
The design system is DESIGN.md; the computable parts of it -- every token in
all three theme scopes -- are pinned in forge/tests/test_factory_board.py.
-->
<style>
  /* ---- design tokens: the committed palette, in all three theme scopes.
     The two dark scopes are byte-identical to each other by construction --
     the toggle beats the OS setting in both directions, neither drifts. ---- */
  :root {{
    color-scheme: light;
    --surface: #fcfcfb;
    --plane: #f9f9f7;
    --ink: #0b0b0b;
    --ink-2: #52514e;
    --muted: #898781;
    --grid: #e1e0d9;
    --axis: #c3c2b7;
    --hair: rgba(11, 11, 11, 0.10);
    --wash: rgba(11, 11, 11, 0.035);
    --shadow: 0 1px 2px rgba(11, 11, 11, 0.06);
    --pass: #0ca30c;
    --warn: #fab219;
    --fail: #d03b3b;
    --pass-ink: #006300;
    --warn-ink: #8a5a00;
    --fail-ink: #b42318;
    --pass-tint: rgba(12, 163, 12, 0.10);
    --warn-tint: rgba(250, 178, 25, 0.16);
    --fail-tint: rgba(208, 59, 59, 0.10);
  }}
  :root[data-theme="dark"] {{
    color-scheme: dark;
    --surface: #1a1a19;
    --plane: #0d0d0d;
    --ink: #ffffff;
    --ink-2: #c3c2b7;
    --muted: #898781;
    --grid: #2c2c2a;
    --axis: #383835;
    --hair: rgba(255, 255, 255, 0.10);
    --wash: rgba(255, 255, 255, 0.05);
    --shadow: 0 1px 2px rgba(0, 0, 0, 0.4);
    --pass: #0ca30c;
    --warn: #fab219;
    --fail: #d03b3b;
    --pass-ink: #3ecb4a;
    --warn-ink: #fab219;
    --fail-ink: #f2655c;
    --pass-tint: rgba(12, 163, 12, 0.16);
    --warn-tint: rgba(250, 178, 25, 0.16);
    --fail-tint: rgba(208, 59, 59, 0.20);
  }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      color-scheme: dark;
      --surface: #1a1a19;
      --plane: #0d0d0d;
      --ink: #ffffff;
      --ink-2: #c3c2b7;
      --muted: #898781;
      --grid: #2c2c2a;
      --axis: #383835;
      --hair: rgba(255, 255, 255, 0.10);
      --wash: rgba(255, 255, 255, 0.05);
      --shadow: 0 1px 2px rgba(0, 0, 0, 0.4);
      --pass: #0ca30c;
      --warn: #fab219;
      --fail: #d03b3b;
      --pass-ink: #3ecb4a;
      --warn-ink: #fab219;
      --fail-ink: #f2655c;
      --pass-tint: rgba(12, 163, 12, 0.16);
      --warn-tint: rgba(250, 178, 25, 0.16);
      --fail-tint: rgba(208, 59, 59, 0.20);
    }}
  }}

  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; }}
  body {{
    background: var(--plane); color: var(--ink);
    font: 14px/1.6 -apple-system, BlinkMacSystemFont, "SF Pro Text",
          "Segoe UI", Inter, Roboto, system-ui, sans-serif;
    font-variant-numeric: tabular-nums;
    -webkit-font-smoothing: antialiased;
  }}
  ::selection {{ background: var(--ink); color: var(--plane); }}

  #page {{ max-width: 1080px; margin: 0 auto; padding: 40px 40px 120px; }}
  @media (max-width: 720px) {{ #page {{ padding: 22px 16px 90px; }} }}

  a, button, input, select, summary {{
    font: inherit; color: inherit;
  }}
  button {{
    cursor: pointer; background: var(--surface); border: 1px solid var(--hair);
    border-radius: 8px; padding: 5px 13px; font-size: 12.5px; color: var(--ink-2);
  }}
  button:hover {{ border-color: var(--ink-2); color: var(--ink); }}
  a:focus-visible, button:focus-visible, summary:focus-visible {{
    outline: 2px solid var(--ink); outline-offset: 2px;
  }}

  /* ---------- header ---------- */
  header h1 {{
    font-size: 22px; font-weight: 650; letter-spacing: -0.02em;
    margin: 0 0 6px; line-height: 1.2;
  }}
  .runline {{
    display: flex; align-items: center; flex-wrap: wrap; gap: 14px 20px;
    color: var(--muted); font-size: 12px; margin: 0 0 4px;
  }}
  .runline .stamp {{ color: var(--ink-2); }}
  .runline .age {{ color: var(--muted); }}
  .controls {{ display: flex; align-items: center; gap: 8px; margin-left: auto; }}
  #stale-flag {{ display: none; }}
  #stale-flag.show {{ display: inline-flex; }}

  /* ---------- status badges: color + icon + word, always all three ---------- */
  .badge {{
    display: inline-flex; align-items: center; gap: 5px;
    padding: 2px 9px; border-radius: 999px;
    font-size: 12px; font-weight: 600; white-space: nowrap;
    line-height: 1.5;
  }}
  .badge .ic {{ font-size: 10.5px; line-height: 1; }}
  .badge.pass    {{ background: var(--pass-tint); color: var(--pass-ink); }}
  .badge.fail    {{ background: var(--fail-tint); color: var(--fail-ink); }}
  .badge.warn    {{ background: var(--warn-tint); color: var(--warn-ink); }}
  .badge.neutral {{ background: var(--hair); color: var(--ink-2); }}
  .badge.pending {{ background: transparent; color: var(--ink-2);
                   border: 1px dashed var(--hair); }}

  /* ---------- legend ---------- */
  .legend {{
    display: flex; flex-wrap: wrap; gap: 10px 16px; align-items: center;
    margin: 14px 0 16px; font-size: 12px; color: var(--ink-2);
  }}
  .legend .key {{ display: inline-flex; align-items: center; gap: 6px; }}

  .panel-title {{
    font-size: 14px; font-weight: 650; color: var(--ink);
    margin: 28px 0 4px; letter-spacing: -0.01em;
  }}
  .panel-title .sub {{ font-weight: 400; color: var(--ink-2); font-size: 12.5px; }}

  /* ---------- the stage grid: one panel, scrolls in itself ---------- */
  .tabwrap {{
    overflow-x: auto; background: var(--surface);
    border: 1px solid var(--hair); border-radius: 10px;
    box-shadow: var(--shadow); margin-top: 10px;
  }}
  table.board {{ border-collapse: collapse; width: 100%; font-size: 13.5px; }}
  table.board th {{
    text-align: left; font-weight: 500; font-size: 12px; color: var(--muted);
    padding: 10px 14px 8px; border-bottom: 1px solid var(--hair);
    white-space: nowrap; position: sticky; top: 0; background: var(--surface);
  }}
  table.board td {{
    padding: 9px 14px; vertical-align: middle;
    white-space: nowrap; border-bottom: 1px solid var(--hair);
  }}
  table.board tr:last-child td {{ border-bottom: none; }}
  table.board tr:hover td {{ background: var(--wash); }}
  table.board td.num {{ text-align: right; }}

  .slug {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
          font-size: 11.5px; color: var(--ink); }}
  .stagelab {{ color: var(--ink-2); }}
  .updated {{ color: var(--muted); font-size: 12px; }}
  .spend {{ color: var(--ink-2); }}
  .spend .of {{ color: var(--muted); }}

  .cmd-row {{ display: flex; align-items: center; gap: 8px; }}
  .cmd-row code {{
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 11.5px; background: var(--wash); border: 1px solid var(--hair);
    border-radius: 7px; padding: 3px 8px; color: var(--ink);
  }}
  .cmd-row button {{ padding: 3px 10px; font-size: 11.5px; }}
  .no-action {{ color: var(--muted); }}
  .empty-state {{ color: var(--ink-2); }}

  .foot-note {{ color: var(--muted); font-size: 12px; margin: 14px 0 0; max-width: 78ch; }}

  @media (prefers-reduced-motion: no-preference) {{
    #page {{ animation: settle 0.22s cubic-bezier(0.16, 1, 0.3, 1); }}
  }}
  @keyframes settle {{
    from {{ opacity: 0; transform: translateY(4px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
  }}
</style>
</head>
<body>
<div id="page">
  <header>
    <h1>Factory board</h1>
    <div class="runline">
      <span>generated <span class="stamp" id="generated-value">{generated}</span></span>
      <span class="age" id="age-value"></span>
      <span class="badge warn" id="stale-flag"><span class="ic" aria-hidden="true">▲</span>stale — the orchestrator has not re-rendered this file recently</span>
      <span class="controls">
        <button type="button" id="theme-btn" aria-pressed="false">Dark theme</button>
        <button type="button" id="pause-btn" aria-pressed="false">Pause auto-refresh</button>
      </span>
    </div>
  </header>

  <h2 class="panel-title">Queue<span class="sub"> — every job, its stage, and the command that unblocks it</span></h2>

  <div class="legend" id="legend" aria-label="stage legend"></div>

  <div class="tabwrap">
    <table class="board" id="board-table">
      <thead><tr id="board-head"></tr></thead>
      <tbody id="board-body"></tbody>
    </table>
  </div>

  <p class="foot-note">The board renders state and, where a human is the next actor, the exact
  command that would move the job forward. It never runs that command and never claims a
  transition happened — the next reload of this file is the only thing that can confirm one did.</p>
</div>

<script type="application/json" id="board-data">{data}</script>
<script>
"use strict";

/* ================= plumbing ================= */
const $ = (sel, el) => (el || document).querySelector(sel);
const esc = s => String(s).replace(/[&<>"]/g,
  c => ({{"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}}[c]));

/* Status is carried by three channels at once -- color, icon, and word --
   so it survives colorblindness, grayscale printing, and forced-colors.
   `badge()` is the only function on this page that paints a status; every
   caller below goes through it, including the legend and every stage cell. */
const ICONS = {{pass: "✓", fail: "✕", warn: "▲"}};
const FALLBACK_ICONS = {{neutral: "●", pending: "—"}};

function badge(kind, label) {{
  const icon = ICONS[kind] || FALLBACK_ICONS[kind] || "•";
  return `<span class="badge ${{kind}}"><span class="ic" aria-hidden="true">${{icon}}</span>${{esc(label)}}</span>`;
}}

/* The five stage-cell states `stage_cell()` can return, in legend order, the
   badge kind each paints as, and the word the legend and every cell in that
   state spell out. "pending" covers both "not started" and "never reached":
   it is named "not run" and painted dimmed rather than left blank, so an
   unreached stage reads as an explicit absence, never a borrowed pass. */
const STAGE_STATES = [
  {{state: "passed",  kind: "pass",    label: "gate-passed"}},
  {{state: "running", kind: "neutral", label: "running"}},
  {{state: "failed",  kind: "fail",    label: "gate-failed"}},
  {{state: "parked",  kind: "warn",    label: "parked for a human"}},
  {{state: "pending", kind: "pending", label: "not run"}},
];
const STAGE_INFO = Object.fromEntries(STAGE_STATES.map(s => [s.state, s]));

/* Job-level statuses, mapped onto the same three-channel vocabulary. `queued`
   reads the same as an unreached stage -- nothing has happened yet, so it is
   dimmed rather than colored. `running` is active and uncolored: neither a
   verdict nor a problem. The awaiting-* gates and `stuck` need a human, so
   they paint as warn; a shipped family passed, and quarantined, blocked, and
   abandoned are the three ways a family ends without shipping. */
const STATUS_KIND = {{
  "queued": "pending",
  "running": "neutral",
  "awaiting-spec-approval": "warn",
  "awaiting-release-review": "warn",
  "stuck": "warn",
  "shipped": "pass",
  "quarantined": "fail",
  "blocked": "fail",
  "abandoned": "fail",
}};

function statusLabel(status) {{
  return status.replace(/-/g, " ");
}}

/* ================= rendering ================= */

function renderLegend() {{
  const el = $("#legend");
  el.innerHTML = STAGE_STATES.map(s => `<span class="key">${{badge(s.kind, s.label)}}</span>`).join("");
}}

function renderHead(lastStage) {{
  const head = $("#board-head");
  const stageHeads = [];
  for (let n = 1; n <= lastStage; n++) stageHeads.push(`<th class="num">${{n}}</th>`);
  head.innerHTML = `<th>job</th><th>status</th><th>stage</th><th>updated</th>`
    + `<th class="num">spend</th>${{stageHeads.join("")}}<th>if a human is next</th>`;
}}

function formatTokens(n) {{
  return n.toLocaleString("en-US");
}}

function stageCellHtml(row, n) {{
  const cellState = row.cells[n - 1];
  const info = STAGE_INFO[cellState];
  const count = row.attempt_counts ? row.attempt_counts[n - 1] : 0;
  let label = info.label;
  /* Annotate the exception, not the rule (DESIGN.md): a first attempt that
     passes or fails needs no count beside it. Only once a stage has been
     retried does "attempt N of the cap" become information a reader needs,
     e.g. a gate that has failed twice with one attempt left before the job
     parks stuck. */
  if (count > 1) label = `${{label}} — attempt ${{count}} of ${{row.cap}}`;
  return `<td>${{badge(info.kind, label)}}</td>`;
}}

function jobRowHtml(row, lastStage) {{
  const kind = STATUS_KIND[row.status] || "neutral";
  const cells = [];
  for (let n = 1; n <= lastStage; n++) cells.push(stageCellHtml(row, n));
  const action = row.command
    ? `<div class="cmd-row"><code>${{esc(row.command)}}</code>`
      + `<button type="button" class="copy-btn" data-cmd="${{esc(row.command)}}">Copy</button></div>`
    : `<span class="no-action">—</span>`;
  return `<tr>`
    + `<td class="slug">${{esc(row.job)}}</td>`
    + `<td>${{badge(kind, statusLabel(row.status))}}</td>`
    + `<td class="stagelab">stage ${{row.stage}} of ${{lastStage}}</td>`
    + `<td class="updated">${{esc(row.updated)}}</td>`
    + `<td class="num spend">${{formatTokens(row.spend)}}<span class="of"> / ${{formatTokens(row.budget)}}</span></td>`
    + cells.join("")
    + `<td>${{action}}</td>`
    + `</tr>`;
}}

function renderBody(rows, lastStage) {{
  if (!rows.length) {{
    // The same "no jobs" wording cli.cmd_status uses for an empty root --
    // a bare header row with nothing under it reads as broken, not empty.
    // This is prose a reader must read, not the em-dash placeholder
    // jobRowHtml paints at --muted, so it gets its own class at --ink-2
    // (DESIGN.md requires 4.5:1 for prose; --muted is 3.41-3.50:1).
    const cols = 6 + lastStage;
    $("#board-body").innerHTML = `<tr><td colspan="${{cols}}" class="empty-state">`
      + `no jobs queued yet -- run `
      + `<code>python -m forge.factory.cli queue &lt;charter-dir&gt;</code> to add one</td></tr>`;
    return;
  }}
  $("#board-body").innerHTML = rows.map(r => jobRowHtml(r, lastStage)).join("");
  for (const btn of document.querySelectorAll(".copy-btn")) {{
    btn.addEventListener("click", async () => {{
      const text = btn.dataset.cmd;
      try {{
        await navigator.clipboard.writeText(text);
      }} catch {{
        const area = document.createElement("textarea");
        area.value = text;
        area.style.position = "fixed";
        area.style.opacity = "0";
        document.body.appendChild(area);
        area.select();
        try {{ document.execCommand("copy"); }} catch {{}}
        area.remove();
      }}
      const was = btn.textContent;
      btn.textContent = "Copied";
      setTimeout(() => {{ btn.textContent = was; }}, 1500);
    }});
  }}
}}

/* ================= staleness: the generated stamp ticks against wall time
   so a stopped orchestrator reads as stale rather than as calm, even though
   this static file itself never changes once the browser has it. ================= */

function formatAge(totalSeconds) {{
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  if (m === 0) return `${{s}}s ago`;
  if (m < 60) return `${{m}}m ${{s}}s ago`;
  const h = Math.floor(m / 60);
  return `${{h}}h ${{m % 60}}m ago`;
}}

function tickAge(generatedIso, staleAfterSeconds) {{
  const genMs = Date.parse(generatedIso);
  if (Number.isNaN(genMs)) return;
  const secs = Math.max(0, Math.round((Date.now() - genMs) / 1000));
  $("#age-value").textContent = `(${{formatAge(secs)}})`;
  $("#stale-flag").classList.toggle("show", secs >= staleAfterSeconds);
}}

/* ================= the refresh timer, with a pause the reader controls ================= */

const REFRESH_SECONDS = {refresh_seconds};
let paused = false;
let reloadTimer = null;

function scheduleReload() {{
  if (reloadTimer) clearTimeout(reloadTimer);
  if (!paused) reloadTimer = setTimeout(() => location.reload(), REFRESH_SECONDS * 1000);
}}

function initControls() {{
  const pauseBtn = $("#pause-btn");
  pauseBtn.addEventListener("click", () => {{
    paused = !paused;
    pauseBtn.textContent = paused ? "Resume auto-refresh" : "Pause auto-refresh";
    pauseBtn.setAttribute("aria-pressed", String(paused));
    scheduleReload();
  }});

  const themeBtn = $("#theme-btn");
  const stored = (() => {{ try {{ return localStorage.getItem("factory-board-theme"); }} catch {{ return null; }} }})();
  if (stored === "dark" || stored === "light") {{
    document.documentElement.setAttribute("data-theme", stored);
    themeBtn.textContent = stored === "dark" ? "Light theme" : "Dark theme";
    themeBtn.setAttribute("aria-pressed", String(stored === "dark"));
  }}
  themeBtn.addEventListener("click", () => {{
    const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    themeBtn.textContent = next === "dark" ? "Light theme" : "Dark theme";
    themeBtn.setAttribute("aria-pressed", String(next === "dark"));
    try {{ localStorage.setItem("factory-board-theme", next); }} catch {{}}
  }});
}}

/* ================= startup: the embedded snapshot ================= */
/* Last in the file on purpose: it runs immediately, so everything it touches
   must already be declared above it. */

(function start() {{
  const raw = $("#board-data").textContent;
  const data = JSON.parse(raw);
  const lastStage = data.rows.length ? data.rows[0].cells.length : 10;

  renderLegend();
  renderHead(lastStage);
  renderBody(data.rows, lastStage);
  initControls();

  const staleAfter = Math.max(300, REFRESH_SECONDS * 3);
  tickAge(data.generated, staleAfter);
  setInterval(() => tickAge(data.generated, staleAfter), 1000);

  scheduleReload();
}})();
</script>
</body>
</html>
"""
