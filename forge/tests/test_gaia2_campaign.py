"""Campaign selection and summary shape -- the judge-confound guards.

The v3 reading established two facts the tooling then had no way to express:
only 5 of the 37 grid scenarios are script-judgeable, and the soft judge's
column is all zeros, so every cross-arm comparison rides on those 5. The
campaign needed a way to spend a seed only where the deterministic verifier
grades (`--scripted-only`), and the summary needed to stop publishing pooled
per-arm rates that mix two graders over disjoint scenario populations --
pooled numbers in that shape were misread twice in one sitting, by the
person holding the full context.
"""

from pathlib import Path
from types import SimpleNamespace

from forge.gaia2.grid import eligible
from scripts.gaia2_campaign_summary import summarize

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def span(usable=True, seamful=True, reply_conditioned=False, roster_blind=()):
    return SimpleNamespace(usable=usable, seamful=seamful,
                           reply_conditioned=reply_conditioned,
                           roster_blind=roster_blind)


# -- eligible: admission plus the judge-uniform restriction -----------------


def test_inadmissible_scenarios_stay_out_regardless_of_the_flag():
    for flag in (False, True):
        assert not eligible(span(usable=False), scripted_only=flag)
        assert not eligible(span(seamful=False), scripted_only=flag)


def test_the_full_grid_keeps_reply_conditioned_scenarios():
    assert eligible(span(reply_conditioned=True), scripted_only=False)
    assert eligible(span(reply_conditioned=False), scripted_only=False)


def test_scripted_only_drops_exactly_the_soft_judged_population():
    assert not eligible(span(reply_conditioned=True), scripted_only=True)
    assert eligible(span(reply_conditioned=False), scripted_only=True)


def test_a_roster_blind_scenario_never_runs():
    # v4 bought four guaranteed failures on scenario_universe_24_tg3h3h: its
    # gold attachment lives in Files, and Files is not on the roster, so no
    # seat -- control included -- could ever produce the required emails. A
    # scenario whose partition provably omits a consumed fact is excluded
    # from every grid, under either judge.
    blind = (("Emails", "send_email", "attachment_paths"),)
    for flag in (False, True):
        assert not eligible(span(roster_blind=blind), scripted_only=flag)


# -- summarize: the per-arm x judge split -----------------------------------


def row(cell_type, judge, success, scenario="s1", **extra):
    base = {
        "scenario_id": scenario, "cell_type": cell_type,
        "config": "open-docs-binf" if cell_type == "control" else "star-docs-binf",
        "judge": judge, "success": success, "partial_reward": None,
        "pivot_kind": None, "delegation_economy_reward": None,
    }
    base.update(extra)
    return base


def test_each_arm_is_split_by_judge_not_only_pooled():
    # The exact shape of the v3 misreading: an arm whose only successes are
    # scripted must show the soft judge's zero *inside the arm's own entry*,
    # not pooled away into a plausible-looking overall rate.
    rows = [
        row("discovery", "scripted", True, scenario="s1"),
        row("discovery", "scripted", True, scenario="s2"),
        row("discovery", "gpt-5.6-sol", False, scenario="s3"),
        row("discovery", "gpt-5.6-sol", False, scenario="s4"),
    ]
    s = summarize(rows)
    assert s["discovery"]["cells"] == 4 and s["discovery"]["success"] == 2
    assert s["discovery"]["by_judge"]["scripted"] == {"cells": 2, "success": 2}
    assert s["discovery"]["by_judge"]["gpt-5.6-sol"] == {"cells": 2, "success": 0}


def test_the_overall_judge_totals_survive():
    rows = [row("control", "scripted", True),
            row("economy", "gpt-5.6-sol", False, scenario="s2")]
    s = summarize(rows)
    assert s["by_judge"]["scripted"] == {"cells": 1, "success": 1}
    assert s["by_judge"]["gpt-5.6-sol"] == {"cells": 1, "success": 0}


# -- the episode client must not be able to hang forever --------------------


def test_the_episode_client_sets_an_explicit_timeout_and_retry_budget():
    # The v4 campaign finished 18 cells in ~100 minutes and then sat for nine
    # hours on two episodes blocked in SSL_read -- an API connection died and
    # `OpenAI()` at library defaults waited on the dead socket indefinitely.
    # A paid campaign must fail a request in minutes and retry on a fresh
    # connection, not wait overnight for bytes that will never come.
    import ast
    from pathlib import Path

    src = Path("scripts/gaia2_cell_run.py").read_text()
    calls = [n for n in ast.walk(ast.parse(src))
             if isinstance(n, ast.Call)
             and getattr(n.func, "id", getattr(n.func, "attr", "")) == "OpenAI"]
    assert calls, "gaia2_cell_run.py no longer constructs the OpenAI client?"
    for call in calls:
        kwargs = {kw.arg for kw in call.keywords}
        assert {"timeout", "max_retries"} <= kwargs, (
            f"OpenAI(...) at line {call.lineno} lacks an explicit timeout / "
            f"max_retries; a dead connection hangs the episode forever"
        )


# -- the credit probe writes label-scoped evidence --------------------------


def test_a_labelled_credit_run_cannot_clobber_the_cited_evidence():
    # Found the expensive way: `gaia2_credit_probe --label v3` overwrote
    # sweep/gaia2_credit.json -- the full campaign's committed evidence, the
    # file the README, both papers, and the viewer cite -- while its note
    # went on claiming "full-campaign". The unqualified name belongs to the
    # full campaign; every other label gets its own file.
    from scripts.gaia2_credit_probe import dest_for, note_for

    assert dest_for("full").name == "gaia2_credit.json"
    assert dest_for("v3").name == "gaia2_v3_credit.json"
    assert dest_for("v3") != dest_for("full")
    assert "v3" in note_for("v3") and "full-campaign" not in note_for("v3")


def test_direct_cell_run_refuses_a_blind_scenario_before_spending():
    # eligible() protects the campaign path, but scripts.gaia2_cell_run is
    # the documented single-cell entry point, and it checked only
    # span.usable -- a directly invoked blind scenario would still buy a
    # guaranteed-failure episode. The refusal must fire before the
    # .venv-gaia2 imports and before any model call, so it works (and is
    # testable) under any interpreter.
    import pytest

    from scripts.gaia2_cell_run import main

    fixture = "forge/tests/fixtures/gaia2/blind.json"
    with pytest.raises(SystemExit, match="roster-blind"):
        main(["--scenario", fixture, "--ability", "control"])


def test_the_blind_refusal_names_each_missing_fact_once():
    # s24 has two gold emails, each attaching the same file, so roster_blind
    # honestly carries two facts -- and the refusal printed "attachment_paths
    # needs 'wikipedia_41.txt' (only in Files)" twice. The data keeps every
    # consuming write; the message names each distinct fact once.
    import json

    import pytest

    from scripts.gaia2_cell_run import main

    fixture = json.loads(
        open("forge/tests/fixtures/gaia2/blind.json").read())
    fixture["events"].append(json.loads(json.dumps(
        next(e for e in fixture["events"]
             if e["class_name"] == "OracleEvent")
    )) | {"event_id": "OracleEvent-AGENT-fixture-2"})
    path = "forge/tests/fixtures/gaia2/.blind_twice.json"
    open(path, "w").write(json.dumps(fixture))
    try:
        with pytest.raises(SystemExit) as exc:
            main(["--scenario", path, "--ability", "control"])
        message = str(exc.value)
        assert message.count("lease_agreement_2023.txt") == 1, message
    finally:
        import os
        os.unlink(path)


# -- the producers refresh the viewer themselves ---


def test_the_campaign_refreshes_the_viewer_after_its_pool_and_never_on_dry_run():
    src = (_SCRIPTS / "gaia2_campaign.py").read_text()
    assert "from scripts.embed_logs import try_refresh" in src
    assert "try_refresh(args.label)" in src
    assert src.index("campaign complete") < src.index("try_refresh(args.label)")
    dry = src.index("if args.dry_run:")
    assert dry < src.index("try_refresh(args.label)")
    assert "return" in src[dry:src.index("def run_one")], "--dry-run must return early"


def test_the_summary_and_credit_probes_refresh_after_writing_their_evidence():
    for name in ("gaia2_campaign_summary.py", "gaia2_credit_probe.py"):
        src = (_SCRIPTS / name).read_text()
        assert "from scripts.embed_logs import try_refresh" in src, name
        assert "try_refresh(args.label)" in src, name
        assert src.index("dest.write_text(") < src.index("try_refresh(args.label)"), name


# -- the campaign renders every cell before it runs any -----------------------


def test_the_campaign_renders_the_grid_after_the_dry_run_return_and_before_any_job():
    src = (_SCRIPTS / "gaia2_campaign.py").read_text()
    assert "from forge.gaia2.harbor import render_grid" in src
    call = src.index("render_grid(grid, ROOT / \"tasks\")")
    dry = src.index("if args.dry_run:")
    assert dry < call, "--dry-run must return before anything is rendered"
    assert call < src.index("def run_one"), "render before the pool is built"
    assert "--no-render" not in src, "rendering is not optional"


def test_the_campaign_reports_what_it_rendered():
    src = (_SCRIPTS / "gaia2_campaign.py").read_text()
    assert 'print(f"rendered {len(rendered)} tasks under tasks/")' in src
