"""Gaia2 (Meta ARE) substrate adapter: mining only, so far.

The runtime, sandbox and Harbor packaging layers are AppWorld-shaped and do
not port; the mining rules do. See `forge/gaia2/mine.py` for how roster and
seam derivation change when the ground truth is gold write actions instead
of reference code.
"""

from forge.gaia2.mine import (
    Gaia2Span,
    GoldWrite,
    Seam,
    admit,
    derive_roster,
    gold_writes,
    information_seams,
    user_text,
)

__all__ = [
    "Gaia2Span",
    "GoldWrite",
    "Seam",
    "admit",
    "derive_roster",
    "gold_writes",
    "information_seams",
    "user_text",
]
