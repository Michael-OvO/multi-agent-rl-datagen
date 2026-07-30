"""The reply-conditioning tag, pinned against the scenario that exposed it.

scenario_universe_28_znpabl's reply emails depend on oracle events: they
schedule only after the judge validates the agent's first turn. Run under
the scripted judge (no LLM soft-checkers), a paraphrased email never
matches, the replies never arrive, and both audited arms hit
ENVIRONMENT_STOP with phase two unreachable -- a failure no agent could
avoid. The miner now measures this property so admission can see it.
"""

import json
from pathlib import Path

from forge.gaia2.mine import admit, conditioned_env_events

REPO = Path(__file__).resolve().parents[2]


def _scenario(events):
    return {"metadata": {"definition": {"scenario_id": "s"}}, "apps": [],
            "events": events}


def test_an_env_event_depending_on_an_oracle_event_is_conditioned():
    events = [
        {"class_name": "OracleEvent", "event_id": "oracle-1",
         "event_type": "AGENT",
         "action": {"app": "Emails", "function": "send_email", "args": []}},
        {"class_name": "Event", "event_id": "env-1", "event_type": "ENV",
         "dependencies": ["oracle-1"],
         "action": {"app": "Emails", "function": "reply_to_email_from_user",
                    "args": []}},
    ]
    assert conditioned_env_events(_scenario(events)) == 1
    assert admit(_scenario(events)).reply_conditioned


def test_an_env_event_on_the_clock_alone_is_not_conditioned():
    events = [
        {"class_name": "Event", "event_id": "env-1", "event_type": "ENV",
         "dependencies": [],
         "action": {"app": "Cabs", "function": "update_ride_status", "args": []}},
    ]
    assert conditioned_env_events(_scenario(events)) == 0
    assert not admit(_scenario(events)).reply_conditioned


def test_the_two_audited_scenarios_split_exactly_as_the_episodes_showed():
    """30_68r6vs ran to a judged verdict; 28_znpabl froze. The tag must
    separate them, or it does not measure what the audit found."""
    data = REPO / "gaia2_data" / "mini"
    if not data.exists():
        import pytest
        pytest.skip("gaia2_data is not fetched (gitignored)")
    single = json.loads((data / "scenario_universe_30_68r6vs.json").read_text())
    gated = json.loads((data / "scenario_universe_28_znpabl.json").read_text())
    assert not admit(single).reply_conditioned
    assert admit(gated).reply_conditioned
    assert admit(gated).conditioned_env_events == 4  # the four reply emails
