"""Structural difficulty of a Gaia2 scenario, read off its oracle-event DAG.

Gold writes carry dependencies, so every scenario ships its own difficulty
geometry: how many writes, how deep the longest chain, how wide the widest
level. `writes` bounds delegation demand, `depth` is forced sequencing, and
`width` is the parallelism a topology could exploit -- all mechanical, all
free, and all inputs to pricing the economy budget rather than guessing it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from forge.gaia2.structure import structure_of

_FIXTURES = Path(__file__).parent / "fixtures" / "gaia2"


def _load(name: str) -> dict:
    return json.loads((_FIXTURES / f"{name}.json").read_text())


def _oracle(event_id: str, deps: list[str], app: str = "Emails") -> dict:
    return {
        "class_name": "OracleEvent",
        "event_type": "AGENT",
        "event_id": event_id,
        "dependencies": deps,
        "action": {"app": app, "function": "f", "args": []},
    }


def test_single_write_scenario_is_one_deep_one_wide():
    s = structure_of(_load("seamful"))
    assert (s.writes, s.depth, s.width) == (1, 1, 1)


def test_independent_writes_widen_without_deepening():
    # operation.json: two gold writes, both depending only on the USER event.
    s = structure_of(_load("operation"))
    assert (s.writes, s.depth, s.width) == (2, 1, 2)


def test_chained_writes_deepen():
    scenario = {
        "apps": [],
        "events": [
            {"class_name": "Event", "event_type": "USER", "event_id": "u1",
             "dependencies": [], "action": {"app": "AgentUserInterface",
                                            "function": "send_message_to_agent",
                                            "args": []}},
            _oracle("o1", ["u1"]),
            _oracle("o2", ["o1"]),
        ],
    }
    s = structure_of(scenario)
    assert (s.writes, s.depth, s.width) == (2, 2, 1)


def test_dependency_cycles_are_refused_not_looped():
    scenario = {
        "apps": [],
        "events": [_oracle("o1", ["o2"]), _oracle("o2", ["o1"])],
    }
    with pytest.raises(ValueError):
        structure_of(scenario)
