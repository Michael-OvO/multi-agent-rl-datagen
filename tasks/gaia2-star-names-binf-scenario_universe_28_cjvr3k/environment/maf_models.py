"""Model classes, and the rule that a specialist never runs below the Main's.

The v5 sweep ran its Main on gpt-5.6-sol and its specialists on gpt-4.1
("narrow, mechanical work; a cheap model is fine"). sweep/appworld_confound.json
is the run that questioned that: star with strong specialists moved the score,
so the specialist's model class is part of what a cell measures, not an
implementation detail. A cell that quietly downgrades its specialists prices
"gpt-5.6 Main coordinating gpt-4.1 hands" -- a blend no ability column claims.

The rule this module enforces: **the specialist runs at least at the Main's
model class** -- both on the gpt-5.6 series, for example -- and a downgraded
specialist is a hard error at episode start, never a silent config. Class is
a named tier, not a string comparison, because "gpt-5.6-sol" vs "gpt-4.1" is
not lexicographic and a future series will not be either.

Nothing here picks models. It only refuses to run a pairing whose measurement
would be mislabelled.
"""

from __future__ import annotations

#: Known model series, mapped to capability class. Higher is more capable.
#: Longest-prefix wins, so "gpt-5.6-sol" resolves through "gpt-5.6" without
#: its own row. Extend this table when a new series is adopted; unknown names
#: are a hard error rather than a guess, because a guessed class silently
#: relabels every cell that runs under it.
MODEL_CLASSES: dict[str, int] = {
    "gpt-5.6": 2,  # the frontier series the sweeps run the Main on
    "gpt-4.1": 1,  # the workhorse series the v5 specialists ran on
}

#: Suffixes that mark a size-reduced variant of a series. A reduced variant is
#: one class below its series: "gpt-5.6-mini" advertising the 5.6 series does
#: not make it the 5.6 class, and prefix matching alone would say it does.
_REDUCED_SUFFIXES = ("-mini", "-nano")


def model_class(model: str) -> int:
    """The capability class of `model`. Raises on a name the table cannot place."""
    matched = max(
        (prefix for prefix in MODEL_CLASSES if model.startswith(prefix)),
        key=len,
        default=None,
    )
    if matched is None:
        raise ValueError(
            f"unknown model series for {model!r}: add it to forge.models.MODEL_CLASSES "
            "so its class is declared, not guessed"
        )
    rank = MODEL_CLASSES[matched]
    if any(model.endswith(s) or f"{s}-" in model[len(matched):] for s in _REDUCED_SUFFIXES):
        rank -= 1
    return rank


def require_specialist_parity(
    main_model: str, sub_model: str, allow_downgrade: bool = False
) -> None:
    """Refuse a specialist below the Main's model class -- unless told not to.

    Called where the specialist model resolves, so no runtime -- in-process
    sweep or shipped sidecar -- can start an episode whose specialists are a
    class below its Main. Equal class is the floor, not sameness: a stronger
    specialist is allowed (that is the confound run, deliberately labelled).

    `allow_downgrade=True` is the explicit escape hatch for experiments that
    *mean* to run a below-class specialist -- reproducing the v5 sweep's
    gpt-4.1 specialists, or measuring the downgrade itself. It must be typed
    at a call site or on a command line, never defaulted on: an accidental
    downgrade relabels the cell, a deliberate one *is* the label. Both model
    names must still classify -- an unknown name is a hard error either way,
    because "allowed" is not the same as "unexamined".
    """
    main_rank, sub_rank = model_class(main_model), model_class(sub_model)
    if allow_downgrade:
        return
    if sub_rank < main_rank:
        raise ValueError(
            f"specialist model {sub_model!r} (class {sub_rank}) is below the "
            f"Main's {main_model!r} (class {main_rank}): run specialists at "
            "least at the Main's class, e.g. the gpt-5.6 series across all "
            "roles -- or pass the explicit allow-downgrade flag if this "
            "pairing is the experiment"
        )
