"""The generation-job factory: charters in, audited task families out.

Modules:
  * state    -- the JobState schema and its dict round-trip. Imports nothing
                from this package; every other module depends on it.
  * store    -- reading and atomically writing a job directory's state.json.
  * machine  -- the lifecycle transitions as pure functions. Must NOT touch
                the filesystem; store applies what it returns.
  * charter  -- charter.md front-matter parsing and the draft refusal.
  * board    -- renders the queue into a self-contained snapshot page.
  * cli      -- `python -m forge.factory.cli <subcommand>`.
"""

from forge.factory.state import (
    Approval,
    Approvals,
    Attempt,
    Caps,
    JobState,
    Spend,
    state_from_dict,
    state_to_dict,
)

__all__ = [
    "Approval",
    "Approvals",
    "Attempt",
    "Caps",
    "JobState",
    "Spend",
    "state_from_dict",
    "state_to_dict",
]
