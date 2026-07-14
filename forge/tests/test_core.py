from forge.maf.core import reward, transcript_hash


def test_reward_gate_zero_zeroes_reward():
    rb = reward(gate=0, quality=0.9, subscores={})
    assert rb.reward == 0.0 and rb.gate == 0


def test_reward_gate_one_is_quality():
    rb = reward(gate=1, quality=0.75, subscores={"makespan": 8})
    assert rb.reward == 0.75 and rb.subscores["makespan"] == 8


def test_quality_clamped_to_unit_interval():
    assert reward(1, 1.5, {}).quality == 1.0
    assert reward(1, 0.0, {}).quality > 0.0  # (0,1], never exactly 0 when gate=1


def test_transcript_hash_is_stable_and_order_independent():
    a = transcript_hash({"x": 1, "y": [1, 2]})
    b = transcript_hash({"y": [1, 2], "x": 1})
    assert a == b
