"""Gaia2 substrate adapter: mining, runtime, and Harbor packaging.

Gaia2 ships on Meta's Agents Research Environments (the official simulation
harness; import name `are.simulation`). The layers here:

  * `mine.py` -- roster and seam derivation when the ground truth is gold
    write actions instead of reference code.
  * `runtime.py` -- the Main + specialists over a duck-typed world, with the
    waiting verb Gaia2's simulated clock requires. Imports no `are.*`.
  * `are_world.py` -- the world adapter over the official harness. Needs the
    dedicated environment (`.venv-gaia2` locally, the sidecar image in a
    shipped task); nothing here imports it.
  * `harbor.py` + `cli.py` -- render admitted scenarios into Harbor tasks.
"""

from forge.gaia2.mine import (
    DelegationHeuristic,
    Gaia2Span,
    GoldWrite,
    Seam,
    admit,
    delegation_heuristic,
    delegation_target,
    derive_roster,
    gold_writes,
    information_seams,
    user_text,
)

__all__ = [
    "DelegationHeuristic",
    "Gaia2Span",
    "GoldWrite",
    "Seam",
    "admit",
    "delegation_heuristic",
    "delegation_target",
    "derive_roster",
    "gold_writes",
    "information_seams",
    "user_text",
]
