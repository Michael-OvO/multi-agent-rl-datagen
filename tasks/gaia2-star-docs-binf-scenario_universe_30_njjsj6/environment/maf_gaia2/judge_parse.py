"""How the benchmark's judge reads its own checker's answer -- the one place
this repo modifies Gaia2's judge, and the whole of the modification.

Gaia2's soft judge grades prose arguments (message content, subjects, titles,
locations) by asking a checker model and reading its answer for a sentinel:
`"[[True]]" in response`, `"[[False]]" in response`, else no vote, and no vote
is returned as None. `SoftToolJudge.compare` then does `if not checker_fn(...)`,
so a None is recorded as a rejection.

Measured 2026-08-31 by calling those checkers directly on the v6 rejections:
our judge model answers `Evaluation: [[true]]`, lowercase. Neither sentinel
matches, the checker abstains, the abstention is recorded as failure. The model
said PASS and the judge wrote FAIL. Of 30 distinct v6 rejections replayed, 24
were this; the soft judge's 0 of 492 across five campaigns is this.

What changes here: the sentinel match is case-insensitive. What does not: the
oracle, the matching, the hard checks, the checker prompts, and every verdict a
checker actually gave. A checker that said neither sentinel still returns None
-- whether an unreadable answer should count as a veto is a separate decision
and is deliberately not made here.

This module imports nothing from `are.*` so `forge/tests` can pin its
behaviour under the main environment; `are_world.open_world` applies it to the
real checker class.
"""

from __future__ import annotations

#: Stamped on every trajectory beside `judge`, for the same reason
#: `objective_action_contract` is: a rollout graded under this parse must
#: never be read against one graded before it as the same experiment.
JUDGE_PARSE_VERSION = "case-insensitive-v1"


def read_verdict(response, success_str: str, failure_str: str) -> bool | None:
    """The checker's answer, read the way the original reads it -- success
    first, then failure, else unreadable -- but without regard to case."""
    if not response:
        return None
    low = str(response).lower()
    if success_str.lower() in low:
        return True
    if failure_str.lower() in low:
        return False
    return None


def patch_llm_checker(checker_class):
    """Install `read_verdict` as `checker_class.__call__`. Idempotent.

    The body is the original `LLMChecker.__call__` line for line -- the vote
    loop, the majority rule -- with the two substring tests replaced by one
    call to `read_verdict`. Nothing else about how a verdict is formed moves.
    """
    if getattr(checker_class, "_forge_judge_parse", None) == JUDGE_PARSE_VERSION:
        return checker_class

    def __call__(self, user_prompt_args):
        votes = []
        for _ in range(self.num_votes):
            response = self.judge(user_prompt_args)
            verdict = read_verdict(response, self.success_str, self.failure_str)
            if verdict is not None:
                votes.append(verdict)
        if len(votes) == 0:
            return None
        return sum(votes) >= len(votes) / 2

    checker_class.__call__ = __call__
    checker_class._forge_judge_parse = JUDGE_PARSE_VERSION
    return checker_class
