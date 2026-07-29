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
