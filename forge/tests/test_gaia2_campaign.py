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

from types import SimpleNamespace

from scripts.gaia2_campaign import eligible
from scripts.gaia2_campaign_summary import summarize


def span(usable=True, seamful=True, reply_conditioned=False):
    return SimpleNamespace(usable=usable, seamful=seamful,
                           reply_conditioned=reply_conditioned)


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
