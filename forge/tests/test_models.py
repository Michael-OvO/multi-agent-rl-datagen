"""Model-class parity tests.

The v5 sweep ran a gpt-5.6-sol Main over gpt-4.1 specialists, and
sweep/appworld_confound.json showed specialist strength moves the score --
so an unexamined downgrade relabels a cell's measurement. These pin the
rule: class is declared, never guessed, and a specialist below the Main's
class refuses to run.
"""

from pytest import raises

from forge.models import model_class, require_specialist_parity


def test_the_gpt_5_6_series_is_one_class_regardless_of_variant():
    assert model_class("gpt-5.6") == model_class("gpt-5.6-sol")


def test_a_reduced_variant_is_one_class_below_its_series():
    assert model_class("gpt-5.6-mini") == model_class("gpt-5.6") - 1
    assert model_class("gpt-5.6-nano") == model_class("gpt-5.6") - 1


def test_a_specialist_below_the_mains_class_is_a_hard_error():
    with raises(ValueError, match="below the Main's"):
        require_specialist_parity("gpt-5.6-sol", "gpt-4.1")
    with raises(ValueError, match="below the Main's"):
        require_specialist_parity("gpt-5.6", "gpt-5.6-mini")


def test_equal_or_stronger_specialists_are_allowed():
    require_specialist_parity("gpt-5.6-sol", "gpt-5.6")
    require_specialist_parity("gpt-4.1", "gpt-4.1")
    # The confound run, deliberately labelled: stronger is legal.
    require_specialist_parity("gpt-4.1", "gpt-5.6-sol")


def test_an_unknown_model_demands_classification_not_a_guess():
    with raises(ValueError, match="unknown model series"):
        model_class("o9-preview")


def test_the_downgrade_escape_hatch_permits_the_pairing_it_names():
    require_specialist_parity("gpt-5.6-sol", "gpt-4.1", allow_downgrade=True)


def test_the_escape_hatch_still_refuses_a_model_it_cannot_classify():
    # "allowed" is not "unexamined": an unknown name is an error either way,
    # because a class nobody declared cannot be a label on the experiment.
    with raises(ValueError, match="unknown model series"):
        require_specialist_parity("gpt-5.6-sol", "mystery-model",
                                  allow_downgrade=True)
