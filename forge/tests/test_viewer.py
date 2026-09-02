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


def viewer_source(html: str) -> str:
    """The page minus its embedded data line.

    The snapshot is machine-generated JSON carrying arbitrary prose from run
    transcripts, so searching it for an identifier yields false hits. Strip
    exactly that one block and keep everything else -- markup, stylesheet,
    and the whole app script are hand-written and must be searched.
    """
    return re.sub(
        r'(<script type="application/json" id="embedded-logs">).*?(</script>)',
        r"\1\2", html, flags=re.S)


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
    source = viewer_source(viewer_html)
    # Guard the guard: if the app script ever falls outside the searched
    # region, this test silently stops testing anything.
    assert '"use strict"' in source, (
        "the app script must be inside the searched region -- the "
        "snapshot-stripping regex is eating real code")
    survivors = [relic for relic in _FOLDER_CONNECT_RELICS if relic in source]
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


def test_the_signal_row_computes_what_its_chips_report(viewer_html):
    stats = re.search(r"function runStats\(eps\) \{(.*?)\n\}", viewer_html, re.S)
    assert stats, "runStats() is missing"
    body = stats.group(1)
    for key in ("malformed", "blocked", "errors", "worst"):
        assert f"{key}:" in body or f"{key} =" in body, (
            f"runStats() does not compute {key}")
    assert "b.total - a.total" in body, (
        "worst must break ties toward the scenario with more runs")


def test_the_signal_counters_do_not_double_report(viewer_html):
    """A malformed line is a protocol fault, not also a tool fault.

    Both counters walk the same events, so without an explicit exclusion the
    same call feeds the "malformed" chip and the "faulted" chip, and two
    chips a reader reads as disjoint silently overlap.
    """
    fn = re.search(r"function countErrors\(d\) \{(.*?)\n\}", viewer_html, re.S)
    assert fn, "countErrors() is missing"
    assert '!== "malformed"' in fn.group(1), (
        "countErrors must exclude malformed, which countMalformed reports")


def test_signals_are_clickable_filters(viewer_html):
    assert "let issueFilter = null" in viewer_html
    assert 'data-issue=' in viewer_html


def test_the_stat_tiles_stay_gone(viewer_css):
    """Removed 2026-07-28 as unnecessary chrome; do not reintroduce."""
    for gone in (".stats {", ".tile {", ".tile.hero"):
        assert gone not in viewer_css, f"{gone} came back"


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


def test_the_grid_tags_only_the_minority_judge(viewer_html):
    """264 "soft judge" tags on 314 badges is not an annotation, it's noise.

    The grid must call badge() directly (not verdictBadge()) so it can tag
    only the judge that is NOT the scenario set's majority judge -- the
    majority becomes the note's stated default instead of a tag repeated on
    84% of cells. softCount, which used to gate the note's soft-judge
    sentence, is unused now that the note always states a default.
    """
    source = viewer_source(viewer_html)
    grid = re.search(
        r"-- Table 1: the verdict matrix --\s*\*/(.*?)-- Table 2:", source, re.S)
    assert grid, "the grid-building block moved; update this test's anchors"
    body = grid.group(1)
    assert "verdictBadge(" not in body, (
        "the grid must call badge() directly so it can control tagging")
    assert "badge(" in body
    assert "majorityJudge" in body and "judgeLabel(" in body
    assert "softCount" not in source, (
        "softCount is unused once the grid stops tagging every cell")


def test_the_note_does_not_call_the_scripted_judge_official(viewer_html):
    """"Official" is Gaia2's soft judge; the scripted fallback is not it.

    The note states whichever judge is the majority as the default, so the
    phrase has to depend on which one won rather than gluing "official" to
    both.
    """
    source = viewer_source(viewer_html)
    assert 'majorityJudge === "scripted"' in source, (
        "the note must branch on which judge is the majority")
    assert not re.search(r'official \$\{judgeLabel\(majorityJudge\)', source), (
        "the note still calls whichever judge won the majority 'official'")


def test_the_runs_table_shows_which_models_ran(viewer_html):
    """'What models ran this?' is a headline question, not a detail-page one."""
    assert "<th>models</th>" in viewer_html


def test_rows_carry_their_issues_for_the_signal_filter(viewer_html):
    assert "data-issues=" in viewer_html
    assert "issueFilter" in viewer_html
    assert "dataset.issues" in viewer_html


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
    Searches the hand-written source: transcript prose in the embedded
    snapshot could otherwise mask the feature's deletion.
    """
    source = viewer_source(viewer_html)
    assert "d.credit" in source, "the shaping-signals block is gone"
    assert "pivotAt" in source, "the pivot-marking loop is gone"
    assert "pivotflag" in source, "the pivot flag is gone"
    assert 'classList.add("pivot")' in source


def test_the_gold_write_panel_keeps_multi_line_arguments(viewer_html):
    """A wrapped value must not silently end the argument list.

    An email body spanning lines used to break the loop, so every argument
    after it vanished while the panel still read as the complete call.
    """
    fn = re.search(r"function parseRationale\(text\) \{(.*?)\n\}",
                   viewer_html, re.S)
    assert fn, "parseRationale() is missing"
    body = fn.group(1)
    assert "List of matching attempts:" in body, (
        "the argument loop must run to the attempts log, not to the first "
        "line that does not start with a dash")
    assert 'args[args.length - 1] +=' in body, (
        "a wrapped line must fold into the argument above it")
    assert '=== "None"' in body, (
        'a rationale of literal "None" must be treated as absent')


def test_the_ledger_view_sets_a_rail_status(viewer_html):
    """The Shipped-task ledger reuses .turn, so it needs a status too."""
    fn = re.search(r"function renderBreakdownDetail\(content, s\) \{(.*?)\n\}",
                   viewer_html, re.S)
    assert fn, "renderBreakdownDetail() is missing"
    assert 'dataset.status = "plain"' in fn.group(1), (
        "ledger rows draw an uncoloured rail dot without an explicit status")


def test_no_view_still_wears_the_paper_costume(viewer_html):
    """One surface, one design: no leftovers from the evidence-page era.

    Searches the hand-written source: "Table 3:" and its kin can occur inside
    a run's transcript text, which lives in the embedded snapshot.
    """
    source = viewer_source(viewer_html)
    for relic in ('class="draftline"', 'class="colophon"', "Table 3:", "Table 4:"):
        assert relic not in source, f"{relic} survived the redesign"


_DESIGN = _ROOT / "DESIGN.md"


def test_design_doc_describes_the_shipped_palette():
    """A design doc that contradicts the artifact is worse than none."""
    text = _DESIGN.read_text()
    for token in ("#0ca30c", "#d03b3b", "#fab219"):
        assert token in text, f"DESIGN.md never mentions {token}"
    assert "signal red" not in text.lower(), (
        "the one-accent rule was overturned on 2026-07-28")


def test_design_doc_does_not_document_retired_rules():
    """Every refusal the shipped file breaks has to leave the doc with it.

    A rule the artifact contradicts is read as the artifact being wrong, and
    the next reader "fixes" the file back toward the retired system.
    """
    text = _DESIGN.read_text()
    for retired in ("Table N", "dagger", "†", "No-Chrome Rule",
                    "Bold-Figure Rule"):
        assert retired not in text, (
            f"DESIGN.md still documents the retired {retired!r} rule")
    assert not re.search(r"\bTable \d", text), (
        "numbered table captions were retired on 2026-07-28")


def test_the_ledger_header_reports_blocked_and_the_answer(viewer_html):
    """These have no other home in that view.

    The per-turn blocked counts appear in the transcript rows but are summed
    nowhere else, and the ledger has no verdict panel to carry the answer.

    Asserts on the aggregate, not on `l.blocked`: that substring also matches
    the per-turn row template built lower in the same function, so deleting
    the header's sum would leave the old assertion passing.
    """
    fn = re.search(r"function renderBreakdownDetail\(content, s\) \{(.*?)\n\}",
                   viewer_html, re.S)
    assert fn, "renderBreakdownDetail() is missing"
    body = fn.group(1)
    # No DOTALL: the sum and its accumulator must sit on one line together,
    # which the per-turn row template never does.
    assert re.search(r"ledger\.reduce\(.*l\.blocked", body), (
        "the ledger header must sum the per-turn blocked counts")
    assert re.search(r'class="verdict-panel"', body) and "d.answer" in body, (
        "the ledger must still report the final answer in its own panel")


def test_the_ledger_header_escapes_both_of_its_sums(viewer_html):
    """Two fields summed from the ledger must both be escaped before they
    reach innerHTML -- whether the sum is injected inline or first hoisted
    into a variable (as `blocked` is, a few lines above its own `<span>`).

    A naive `[^)]*` regex can't span the reduce call's own arrow-function
    parens (`(n, l) => ...`), so this allows one level of nesting instead.
    """
    fn = re.search(r"function renderBreakdownDetail\(content, s\) \{(.*?)\n\}",
                   viewer_html, re.S)
    assert fn, "renderBreakdownDetail() is missing"
    body = fn.group(1)
    sums = re.findall(r"d\.ledger\.reduce\((?:[^()]|\([^()]*\))*\)", body)
    assert len(sums) >= 2, f"expected two summed fields, found {len(sums)}"
    for s in sums:
        inline = f"esc(String({s}))" in body
        hoisted = re.search(r"const (\w+) = " + re.escape(s), body)
        via_variable = hoisted and f"esc(String({hoisted.group(1)}))" in body
        assert inline or via_variable, (
            f"this sum reaches innerHTML unescaped: {s}")


def test_verdict_panel_headings_and_prose_are_sized_off_the_type_scale(viewer_css):
    """No rule exists for `h4`/`h5`/`ul`/`li`/`p` in the stylesheet, so
    browser defaults apply inside `.verdict-panel` and an instruction's
    `<h5>` renders smaller than its own body text (I4). Scoped so nothing
    else on the page changes, and using only existing tokens."""
    assert re.search(r"\.verdict-panel h4\s*\{", viewer_css), (
        ".verdict-panel needs a sized h4 rule")
    assert re.search(r"\.verdict-panel h5\s*\{", viewer_css), (
        ".verdict-panel needs a sized h5 rule")


def test_no_status_class_paints_nothing(viewer_css):
    """A colour rule whose every match overrides it is dead weight."""
    assert not re.search(r"^\s*\.bad \{", viewer_css, re.M), (
        ".bad's colour was inert -- every match overrode it")


# -- the snapshot carries an index of every episode and the task pool ---------


def test_the_snapshot_loader_adds_index_then_tasks_then_files(viewer_html):
    """A full trajectory in `files` must replace the stub with the same path,
    and addSession keeps the LATER entry -- so the index goes in first."""
    source = viewer_source(viewer_html)
    loader = re.search(r"function loadSnapshot\(\) \{(.*?)\n\}\)\(\);", source, re.S)
    assert loader, "the loadSnapshot IIFE moved; update this test's anchor"
    body = loader.group(1)
    assert "snap.index" in body and "snap.tasks" in body and "snap.files" in body
    assert body.index("snap.index") < body.index("snap.tasks") < body.index("snap.files")
    assert "fullLabel = snap.full_label" in body


def test_the_source_line_names_episodes_campaigns_tasks_and_the_full_label(viewer_html):
    """Anchored inside loadSnapshot itself (I7): the embedded snapshot's
    prose can contain these same substrings, so an unanchored search could
    pass against transcript text rather than the source-line assembly."""
    source = viewer_source(viewer_html)
    loader = re.search(r"function loadSnapshot\(\) \{(.*?)\n\}\)\(\);", source, re.S)
    assert loader, "the loadSnapshot IIFE moved; update this test's anchor"
    body = loader.group(1)
    assert "episodes across" in body
    assert "} tasks" in body
    assert "transcripts for" in body


def test_index_stubs_and_the_campaign_selection_are_page_state(viewer_html):
    source = viewer_source(viewer_html)
    assert "let fullLabel = null;" in source
    assert "let campaignSel = null;" in source


def test_task_records_are_their_own_session_kind(viewer_html):
    source = viewer_source(viewer_html)
    assert 'if (data && data.kind === "forge-task") return "task";' in source
    assert "task: 1" in re.search(r"const order = \{(.*?)\};", source).group(1)


# -- a picked or dropped file replaces its index stub, not duplicates it -----


def test_a_picked_file_resolves_against_a_known_stub_by_basename(viewer_html):
    """`File.webkitRelativePath` is "" for a plain multi-file pick and for
    `dataTransfer.files`, so a picked rollout must be resolved against a
    known stub's path by basename before `addSession` de-duplicates by exact
    `path` -- otherwise it lands as a second session instead of replacing
    the stub (C1). Every breakdown shares the basename `breakdown.json`, so
    the match must require exactly one hit."""
    source = viewer_source(viewer_html)
    fn = re.search(r"async function addFiles\(fileList\) \{(.*?)\n\}", source, re.S)
    assert fn, "addFiles moved; update this test's anchor"
    body = fn.group(1)
    assert 's.path.endsWith("/" + base)' in body, (
        "a picked basename must be resolved against known session paths")
    assert "hits.length === 1" in body, (
        "an ambiguous basename (e.g. every breakdown.json) must not resolve")


def test_every_credit_field_the_viewer_reads_is_in_the_index_record(viewer_html):
    """Builder and page must agree on the `credit` shape across languages.

    A key the viewer reads via `d.credit.<key>` but `index_record` does not
    copy into a stub renders as "undefined" -- exactly C2's bug, for whatever
    key regresses next. Pins the two languages together by reading the
    builder's own tuple rather than restating it here."""
    source = viewer_source(viewer_html)
    read_keys = set(re.findall(r"d\.credit\.([a-zA-Z_]+)", source))
    assert read_keys, "no d.credit.<key> reads found; the anchor moved"
    embed_src = (_ROOT / "scripts" / "embed_logs.py").read_text()
    tup = re.search(
        r'"credit":\s*\(\{k: credit\.get\(k\) for k in\s*\((.*?)\)\}',
        embed_src, re.S)
    assert tup, "index_record's credit tuple moved; update this test's anchor"
    builder_keys = set(re.findall(r'"([a-zA-Z_]+)"', tup.group(1)))
    missing = read_keys - builder_keys
    assert not missing, (
        f"the viewer reads d.credit.{missing} but embed_logs.py's "
        "index_record never copies it into the stub")


# -- readable across campaigns: one at a time by default ----------------------


def test_the_runs_view_offers_a_campaign_picker_in_the_filter_line(viewer_html):
    source = viewer_source(viewer_html)
    assert 'id="campaignpick"' in source
    assert "all campaigns" in source
    header = re.search(r"<header>(.*?)</header>", viewer_html, re.S).group(1)
    assert "campaignpick" not in header


def test_the_picker_defaults_to_the_embedded_campaign(viewer_html):
    source = viewer_source(viewer_html)
    assert "campaignSel = fullLabel" in source
    assert 'campaignSel === "*"' in source


def test_the_picker_groups_campaigns_apart_from_one_run_probes(viewer_html):
    """13 labels + '(unlabelled)' + 'all campaigns' as 15 flat entries is
    unreadable when 8 of them are one-run probes; group with native
    <optgroup> instead of hiding anything (picker ruling, option 1)."""
    source = viewer_source(viewer_html)
    assert "const CAMPAIGN_MIN_EPISODES = 10;" in source
    assert '<optgroup label="campaigns">' in source
    assert '<optgroup label="probes">' in source


# -- which parse graded each verdict, and success by judge --------------------


def test_the_grid_states_the_majority_parse_and_tags_only_departures(viewer_html):
    source = viewer_source(viewer_html)
    grid = re.search(
        r"-- Table 1: the verdict matrix --\s*\*/(.*?)-- Table 2:", source, re.S)
    assert grid, "the grid-building block moved; update this test's anchors"
    body = grid.group(1)
    assert "parseLabel(" in body and "majorityParse" in body
    assert "badge(" in body and "verdictBadge(" not in body
    assert "gaia2_v6_judge_parse.json" in body
    assert "majorityParse === STOCK_PARSE" in body


def test_the_parse_helpers_default_to_stock(viewer_html):
    source = viewer_source(viewer_html)
    assert 'const STOCK_PARSE = "stock";' in source
    assert "const parseLabel = d => d.judge_parse || STOCK_PARSE;" in source


def test_the_grid_note_states_success_by_judge_as_a_sentence(viewer_html):
    source = viewer_source(viewer_html)
    assert "judgeSentence" in source
    assert "of ${c.total} passed" in source
    assert '=== "scripted" ? 0 : 1' in source


def test_rows_index_their_parse_for_the_search_box(viewer_html):
    source = viewer_source(viewer_html)
    row = re.search(r'data-text="\$\{esc\(JSON\.stringify\(\[(.*?)\]\)', source, re.S)
    assert row, "the runs-table row's data-text moved"
    assert "parseLabel(d)" in row.group(1)


# -- whether the world ended the episode --------------------------------------


def test_the_stop_helpers_read_the_instrumented_stop_row(viewer_html):
    source = viewer_source(viewer_html)
    assert 'const ENV_STOP = "(environment stopped)";' in source
    assert "const wasStopped = d =>" in source
    assert "function lastStop(d)" in source and '"time_passed" in ev[i]' in source
    assert "return d.stop || null;" in source
    assert "function endedCell(d)" in source
    assert "world stopped at ${t}" in source


def test_the_runs_table_has_an_ended_column_between_issues_and_answer(viewer_html):
    source = viewer_source(viewer_html)
    head = re.search(r"<th>issues</th>(.*?)<th>answer</th>", source, re.S)
    assert head and "<th>ended</th>" in head.group(1)
    assert "${endedCell(d)}" in source


def test_stopped_is_a_disjoint_signal_with_its_own_chip(viewer_html):
    source = viewer_source(viewer_html)
    assert 'wasStopped(d) ? "stopped" : ""' in source
    assert "let malformed = 0, blocked = 0, errors = 0, stopped = 0;" in source
    assert 'key: "stopped", kind: "warn"' in source
    assert "stopped by the world" in source
    fn = re.search(r"function countErrors\(d\) \{(.*?)\n\}", source, re.S).group(1)
    assert "answer" not in fn and "ENV_STOP" not in fn


def test_count_errors_reads_a_precomputed_count_like_count_malformed(viewer_html):
    source = viewer_source(viewer_html)
    fn = re.search(r"function countErrors\(d\) \{(.*?)\n\}", source, re.S).group(1)
    assert 'if (typeof d.errors === "number") return d.errors;' in fn


# -- the episode view: parse, stop line, and a stub for old campaigns ----------


def _episode_fn(viewer_html: str) -> str:
    source = viewer_source(viewer_html)
    fn = re.search(r"function renderEpisode\(content, s\) \{(.*?)\n\}", source, re.S)
    assert fn, "renderEpisode moved"
    return fn.group(1)


def test_the_run_bar_names_the_parse_only_when_the_run_carries_one(viewer_html):
    body = _episode_fn(viewer_html)
    assert "d.judge_parse ? `<span>judge parse <b>" in body


def test_a_stopped_episode_gets_one_credit_style_stop_line(viewer_html):
    body = _episode_fn(viewer_html)
    assert "if (wasStopped(d)) {" in body
    assert 'line.className = "credit";' in body
    assert "simulated seconds used" in body
    assert "no clock recorded for this run" in body
    assert 'line.title = String(st.reason || "");' in body


def test_an_index_stub_renders_a_summary_and_no_transcript(viewer_html):
    body = _episode_fn(viewer_html)
    stub = re.search(r"if \(d\.index_only\) \{(.*?)\n    return;\n  \}", body, re.S)
    assert stub, "renderEpisode needs an index_only branch that returns early"
    assert 'class="abstract"' in stub.group(1)
    assert "open files" in stub.group(1)
    assert body.index("if (d.index_only) {") < body.index('list.className = "transcript";')


# -- an evidence file's summary, above its rows --------------------------------


def test_a_sweep_file_s_summary_renders_above_its_table(viewer_html):
    source = viewer_source(viewer_html)
    fn = re.search(r"function renderSweeps\(content\) \{(.*?)\n\}", source, re.S).group(1)
    assert "s.data.summary" in fn
    assert 'class="note summary"' in fn
    assert "slice(0, 160)" in fn
    assert fn.index('class="note summary"') < fn.index("const draw = () =>")


# -- the task pool: every task, and every run of it --------------------------


def test_tasks_is_the_second_section(viewer_html):
    source = viewer_source(viewer_html)
    secs = re.search(r"const SECTIONS = \[(.*?)\];", source, re.S).group(1)
    assert '["runs", "Runs"], ["tasks", "Tasks"]' in secs.replace("\n", "").replace("  ", " ")
    assert 'if (tab === "tasks") return renderTasks(content);' in source
    assert 'if (s.kind === "task") return renderTaskDetail(content, s);' in source


def test_the_tasks_table_names_what_a_task_is_and_who_it_may_use(viewer_html):
    source = viewer_source(viewer_html)
    fn = re.search(r"function renderTasks\(content\) \{(.*?)\n\}", source, re.S)
    assert fn, "renderTasks is missing"
    body = fn.group(1)
    for col in ("task", "substrate", "configuration", "target", "roster",
                "difficulty", "contract", "runs"):
        assert f"<th>{col}</th>" in body, col
    assert "family" in body and "verdictBadge(" not in body, (
        "the runs cell is a count, not a badge; a substrate is a word, not a colour")
    assert 'wireSearch(fbar, trs, "tasks")' in body, (
        "the tasks table shares the search helper rather than copying the filter block")
    assert "function wireSearch(fbar, trs, noun)" in source


def test_a_task_detail_renders_its_instruction_as_prose_and_its_runs(viewer_html):
    source = viewer_source(viewer_html)
    fn = re.search(r"function renderTaskDetail\(content, s\) \{(.*?)\n\}", source, re.S)
    assert fn, "renderTaskDetail is missing"
    body = fn.group(1)
    assert "mdLite(" in body
    assert "family match" in body
    assert "verdictBadge(" in body, "each run's verdict is a badge"
    assert 'contract <b class="mono">' in body and "d.contract_version" in body, (
        "the bare word 'contract' also matches prose in a task's own "
        "instruction text; anchor on the fact-line markup instead (I7)")
    assert "sessions.findIndex(" in body, "a run row opens its breakdown ledger by path"


def test_render_breakdowns_shares_the_search_helper(viewer_html):
    """renderBreakdowns' inline filter block had become a verbatim copy of
    wireSearch; sharing it is the fix (Minor). renderRuns keeps its own
    inline block -- it is genuinely different code and stays untouched."""
    source = viewer_source(viewer_html)
    fn = re.search(r"function renderBreakdowns\(content\) \{(.*?)\n\}", source, re.S)
    assert fn, "renderBreakdowns is missing"
    body = fn.group(1)
    assert 'wireSearch(fbar, trs, "runs")' in body
    assert "fbar.addEventListener(\"input\", apply)" not in body, (
        "the inline copy of wireSearch should be gone from renderBreakdowns")


def test_substrate_names_is_defined_once_at_module_level(viewer_html):
    """`NAMES` was defined identically inside both renderTasks and
    renderTaskDetail; hoisted to one module-level SUBSTRATE_NAMES (Minor)."""
    source = viewer_source(viewer_html)
    assert source.count('const SUBSTRATE_NAMES = {appworld: "AppWorld", '
                         'gaia2: "Gaia2", "parallel-scheduling": '
                         '"parallel-scheduling"};') == 1
    tasks_fn = re.search(r"function renderTasks\(content\) \{(.*?)\n\}", source, re.S).group(1)
    detail_fn = re.search(r"function renderTaskDetail\(content, s\) \{(.*?)\n\}", source, re.S).group(1)
    assert "const NAMES = " not in tasks_fn
    assert "const NAMES = " not in detail_fn
    assert "SUBSTRATE_NAMES[d.substrate]" in tasks_fn
    assert "SUBSTRATE_NAMES[d.substrate]" in detail_fn


def test_md_lite_escapes_before_it_marks_up(viewer_html):
    source = viewer_source(viewer_html)
    fn = re.search(r"function mdLite\(text\) \{(.*?)\n\}", source, re.S)
    assert fn, "mdLite is missing"
    body = fn.group(1)
    assert body.index("esc(") < body.index("<h4>")
    assert 'class="mono"' in body and "<b>" in body and "<ul>" in body


def test_md_lite_folds_an_indented_continuation_into_its_bullet(viewer_html):
    """A bullet's indented continuation line must extend the `<li>`, not
    close the list and open an orphan paragraph carrying its raw indent
    (I3) -- checked before `if (list) flush();` runs."""
    source = viewer_source(viewer_html)
    fn = re.search(r"function mdLite\(text\) \{(.*?)\n\}", source, re.S)
    assert fn, "mdLite is missing"
    body = fn.group(1)
    assert r"/^\s+\S/.test(raw)" in body, (
        "mdLite must detect an indented continuation line before flushing "
        "the open list")
    assert body.index(r"/^\s+\S/.test(raw)") < body.index("if (list) flush();"), (
        "the continuation check must run before the list-closing branch")


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
    # The reader's preference is read from the summary's click, never from
    # `toggle`: a programmatic open fires `toggle` too and would latch it.
    assert 'drawer.querySelector("summary").addEventListener("click"' in body
    assert "runsDrawerOpen = !drawer.open;" in body
    assert 'addEventListener("toggle"' not in body


def test_the_drawer_summary_hides_the_native_marker_with_the_palette_s_muted(viewer_css):
    assert re.search(r"details\.drawer > summary\s*\{[^}]*list-style: none", viewer_css)
    assert re.search(r"details\.drawer > summary::-webkit-details-marker\s*\{[^}]*display: none", viewer_css)
    assert re.search(r"details\.drawer > summary::before\s*\{[^}]*var\(--muted\)", viewer_css)
    assert "details.drawer[open] > summary::before" in viewer_css


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
