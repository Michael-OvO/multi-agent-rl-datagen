"""The factory board's contract, in the style of test_viewer.py.

The board is the only surface a reader sees the queue through, so what it
must never do matters as much as what it shows: never assert an action
succeeded, never colour a status without also carrying icon and word, never
draw a stage that has not run as anything but an explicit absence.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from forge.factory.board import render_board, stage_cell
from forge.factory.store import discover

FIXTURES = Path(__file__).parent / "fixtures" / "factory" / "genjobs"
STATES = discover(FIXTURES)
GENERATED = "2026-08-10T16:00:00-07:00"


@pytest.fixture(scope="module")
def page():
    return render_board(STATES, generated=GENERATED)


# -- the stage grid ---------------------------------------------------------


def test_a_stage_below_the_cursor_with_a_passed_attempt_reads_passed():
    state = next(s for s in STATES if s.job == "2026-08-02-running-live")
    assert stage_cell(state, 3) == "passed"


def test_the_cursor_stage_with_an_unfinished_attempt_reads_running():
    state = next(s for s in STATES if s.job == "2026-08-02-running-live")
    assert stage_cell(state, 4) == "running"


def test_a_stage_with_a_failed_attempt_reads_failed():
    state = next(s for s in STATES if s.job == "2026-08-04-gate-failed")
    assert stage_cell(state, 7) == "failed"


def test_a_parked_job_reads_parked_at_its_cursor():
    state = next(s for s in STATES if s.job == "2026-08-03-awaiting-spec")
    assert stage_cell(state, 2) == "parked"


def test_a_stage_never_reached_reads_pending_not_borrowed():
    state = next(s for s in STATES if s.job == "2026-08-01-queued-only")
    assert stage_cell(state, 9) == "pending"


# -- the page ---------------------------------------------------------------


def test_the_page_is_self_contained(page):
    assert page.lstrip().startswith("<!doctype html>")
    assert "<script" in page and "</script>" in page
    for forbidden in ("http://", "https://", "src=", "@import"):
        assert forbidden not in page, f"the board must not reference {forbidden}"


def test_every_job_appears_with_its_status(page):
    for state in STATES:
        assert state.job in page
        assert state.status in page


def test_the_generated_timestamp_is_always_on_screen(page):
    assert GENERATED in page, (
        "a stopped orchestrator must read as stale, not as live")


def test_the_page_refreshes_itself(page):
    assert "location.reload" in page
    assert re.search(r"REFRESH_SECONDS\s*=\s*\d+", page)


def test_the_refresh_can_be_paused(page):
    assert "pause" in page.lower(), (
        "a reader inspecting a transcript must be able to stop the reload")


# -- the design system ------------------------------------------------------


def test_the_committed_tokens_are_used_by_name_and_hex(page):
    for token, value in (("--surface", "#fcfcfb"), ("--ink", "#0b0b0b"),
                         ("--muted", "#898781"), ("--pass", "#0ca30c"),
                         ("--warn", "#fab219"), ("--fail", "#d03b3b"),
                         ("--pass-ink", "#006300"), ("--fail-ink", "#b42318")):
        assert f"{token}: {value}" in page, f"{token} must be the committed hex"


def test_all_three_theme_scopes_are_defined(page):
    assert ":root {" in page
    assert '[data-theme="dark"]' in page
    assert "prefers-color-scheme: dark" in page
    assert ':root:not([data-theme="light"])' in page


def test_no_status_is_carried_by_colour_alone(page):
    # Every badge emits an icon AND a word; the icon is hidden from readers
    # who hear the word instead.
    assert 'aria-hidden="true"' in page
    for glyph in ("✓", "✕", "▲"):
        assert glyph in page


def test_the_grid_carries_a_legend_naming_every_state(page):
    for word in ("pending", "running", "gate-passed", "gate-failed",
                 "parked", "not run"):
        assert word in page, f"the legend must name {word!r}"


def test_the_board_states_commands_rather_than_claiming_actions(page):
    assert "python -m forge.factory.cli approve" in page
    for claim in ("Approved!", "Retrying…", "Done!"):
        assert claim not in page, (
            "the board renders; it must never assert an outcome it cannot see")


def test_the_page_is_one_centred_column(page):
    assert "max-width: 1080px" in page
    assert "overflow-x: auto" in page, "the grid scrolls inside its panel"


def test_figures_are_tabular(page):
    assert "font-variant-numeric: tabular-nums" in page


def test_the_approve_command_the_board_advertises_actually_exists():
    # HUMAN_GATES renders "approve <job> --spec/--release" for every job
    # parked at a human gate. If cli.py never registered that subcommand,
    # the board would be advertising a command that raises "invalid choice"
    # -- argparse only exits 0 on --help for a subcommand it recognizes.
    from forge.factory.cli import main as cli_main

    with pytest.raises(SystemExit) as excinfo:
        cli_main(["approve", "--help"])
    assert excinfo.value.code == 0, (
        "'approve' must be a registered subcommand, not an unrecognized "
        "verb the board advertises into a dead end")


def test_the_pending_badge_uses_ink_2_not_muted_for_contrast(page):
    # --muted is 3.41-3.50:1 in the two modes -- DESIGN.md reserves it for
    # de-emphasized labels (timestamps, paths), not for text a reader must
    # actually read. .badge.pending paints the "not run" word shown in most
    # grid cells and the "queued" job status, so it needs an -ink colour.
    match = re.search(r"\.badge\.pending\s*\{[^}]*\}", page)
    assert match, ".badge.pending rule not found"
    assert "var(--ink-2)" in match.group()
    assert "var(--muted)" not in match.group()


def test_an_empty_queue_explains_itself_instead_of_a_bare_header():
    page = render_board([], generated=GENERATED)
    assert "no jobs" in page.lower(), (
        "render_board([]) must explain the empty grid, the way "
        "cli.cmd_status does for an empty root, rather than leaving a "
        "reader staring at a header row and nothing else")


def test_the_empty_state_sentence_is_not_painted_at_muted_contrast():
    # db72396 reused .no-action (var(--muted), 3.41-3.50:1 -- DESIGN.md
    # reserves --muted for de-emphasized labels like the em-dash placeholder
    # in jobRowHtml) for the empty-queue explanatory sentence. That sentence
    # is prose a reader must actually read, which DESIGN.md requires at
    # 4.5:1 -- --ink-2 or an -ink colour, never --muted.
    page = render_board([], generated=GENERATED)
    assert '<td colspan="${cols}" class="no-action">' not in page, (
        "the empty-state <td> must not share .no-action with the em-dash "
        "placeholder in jobRowHtml -- that class is --muted, reserved for "
        "de-emphasized labels, not prose a reader must read")
    match = re.search(r'<td colspan="\$\{cols\}" class="([\w-]+)">', page)
    assert match, "empty-state <td> not found"
    rule = re.search(r"\." + re.escape(match.group(1)) + r"\s*\{[^}]*\}", page)
    assert rule, f".{match.group(1)} rule not found in <style>"
    assert "var(--ink-2)" in rule.group()
    assert "var(--muted)" not in rule.group()
