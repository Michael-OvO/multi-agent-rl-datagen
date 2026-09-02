"""The one place this repo modifies the benchmark's judge, and why.

Measured 2026-08-31 by calling Gaia2's own soft checkers directly on the v6
rejections. `are.simulation.validation.utils.llm_utils.LLMChecker.__call__`
reads the checker model's answer by substring: `"[[True]]" in response`,
`"[[False]]" in response`, else no vote, and no vote returns None. Our judge
model answers `Evaluation: [[true]]` -- lowercase -- so neither sentinel
matches, the checker returns None, and `SoftToolJudge.compare` turns that
None into a rejection with `if not checker_fn(...)`. The model said PASS and
the judge recorded FAIL, on letter case. Replaying all 30 distinct v6
rejections: 24 were a checker returning None; 3 were a real False; 3 passed.
The soft judge scored 0 of 492 across five campaigns because of this.

What is fixed: how the answer is read. What is not: the oracle, the matching,
the hard checks, the checker prompts, and what any checker decided. If it said
pass, pass is recorded; if it said fail, fail is recorded; if it said neither,
the answer is still unreadable and still returns None -- the second defect
(unreadable counted as fail) is a separate decision and a separate change.

`forge/tests` cannot import are_world (it needs `are.*`), so the parse is a
pure function in forge/gaia2/judge_parse.py, tested here, and are_world's
application of it is guarded structurally.
"""

import ast
from pathlib import Path

from forge.gaia2.judge_parse import JUDGE_PARSE_VERSION, read_verdict

S, F = "[[True]]", "[[False]]"


def test_the_exact_response_that_zeroed_the_column_now_reads_as_pass():
    # Captured verbatim from gpt-5.6-sol acting as tone_checker, 2026-08-31.
    response = ("Reasoning: The message is clear, professional, and appropriate "
                "for the recipient.\n\nEvaluation: [[true]]")
    assert read_verdict(response, S, F) is True


def test_the_benchmark_s_own_casing_still_reads_as_it_always_did():
    assert read_verdict("Evaluation: [[True]]", S, F) is True
    assert read_verdict("Evaluation: [[False]]", S, F) is False


def test_any_casing_of_either_sentinel_is_read():
    assert read_verdict("[[TRUE]]", S, F) is True
    assert read_verdict("[[false]]", S, F) is False
    assert read_verdict("[[FaLsE]]", S, F) is False


def test_a_response_with_no_sentinel_is_still_unreadable():
    # Deliberately unchanged: the parse is fixed, the abstention policy is
    # not. This test pins that the fix does not quietly widen into "anything
    # that mentions true".
    assert read_verdict("Evaluation: true", S, F) is None
    assert read_verdict("I think it is fine.", S, F) is None
    assert read_verdict(None, S, F) is None
    assert read_verdict("", S, F) is None


def test_the_success_sentinel_wins_when_both_appear():
    # Mirrors the original's `if success in ... elif failure in ...` order,
    # so a checker that quotes both and concludes pass is read as pass.
    assert read_verdict("not [[False]]; verdict [[True]]", S, F) is True


def test_the_version_is_stamped_and_named_for_what_it_does():
    assert JUDGE_PARSE_VERSION == "case-insensitive-v1"


def test_open_world_applies_the_parse_to_the_real_checker():
    # are_world.py is the one place the world becomes the official harness;
    # if the patch is not applied there, every soft-judged episode silently
    # returns to 0 of N and nothing in this suite would notice.
    source = Path(__file__).parents[1] / "gaia2" / "are_world.py"
    tree = ast.parse(source.read_text())
    open_world = next(n for n in ast.walk(tree)
                      if isinstance(n, ast.FunctionDef) and n.name == "open_world")
    calls = {getattr(n.func, "id", getattr(n.func, "attr", None))
             for n in ast.walk(open_world) if isinstance(n, ast.Call)}
    assert "patch_llm_checker" in calls, \
        "open_world() must call judge_parse.patch_llm_checker before the judge is built"


def test_every_trajectory_records_which_parse_judged_it():
    # Same reason objective_action_contract is stamped: a v7 rollout must
    # never be read against a v6 one as the same experiment.
    source = Path(__file__).parents[2] / "scripts" / "gaia2_cell_run.py"
    text = source.read_text()
    assert '"judge_parse"' in text and "JUDGE_PARSE_VERSION" in text, \
        "gaia2_cell_run must stamp judge_parse: JUDGE_PARSE_VERSION on every record"
