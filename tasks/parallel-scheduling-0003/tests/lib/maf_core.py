"""Core primitives shared by every dimension and by both runtimes.

This module is copied verbatim into each generated task's ``tests/lib`` -- which
Harbor uploads only at verification time, never into the agent's image -- so
that the in-container verifier and the in-process selfcheck grade identically.
It must stay standard-library-only.
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass, field
from typing import Callable, Protocol, runtime_checkable

Rng = random.Random


@dataclass
class RewardBreakdown:
    """The uniform reward shape: ``reward = gate * quality``.

    ``gate`` is a hard 0/1 constraint check; ``quality`` is a (0,1] measure of
    how good a *valid* solution is. ``subscores`` carries dimension-specific
    diagnostics used for RL credit assignment and calibration.
    """

    reward: float
    gate: int
    quality: float
    subscores: dict = field(default_factory=dict)

    def to_json(self) -> dict:
        return {
            "reward": self.reward,
            "gate": self.gate,
            "quality": self.quality,
            "subscores": self.subscores,
        }


def reward(gate: int, quality: float, subscores: dict) -> RewardBreakdown:
    """Build a :class:`RewardBreakdown`, clamping ``quality`` to (0, 1]."""
    q = max(1e-6, min(1.0, float(quality)))
    g = 1 if gate else 0
    return RewardBreakdown(reward=g * q, gate=g, quality=q, subscores=subscores)


def transcript_hash(submission) -> str:
    """Stable, order-independent hash of a JSON-serializable submission."""
    return hashlib.sha256(
        json.dumps(submission, sort_keys=True, default=str).encode()
    ).hexdigest()


# A policy drives an Env (or, for static dimensions, receives the public
# instance) and produces the graded submission. See each dimension's
# ``run_policy`` for how policies are executed.
Policy = Callable[..., object]


@runtime_checkable
class Env(Protocol):
    """Runtime state machine for interactive dimensions."""

    def public_state(self) -> dict:
        """What the agent is allowed to observe."""
        ...

    def submission(self) -> object:
        """The graded artifact/transcript accumulated so far."""
        ...


@runtime_checkable
class Dimension(Protocol):
    """The contract every task family implements.

    Ground-truth fields of an instance are prefixed with ``_`` and are never
    surfaced to the agent (``public`` strips them). ``ORACLE`` and every entry
    in ``CHEATERS`` interact only through the public policy surface.
    """

    NAME: str
    SUBMISSION_FILE: str
    INTERACTIVE: bool
    ORACLE: Policy
    CHEATERS: dict
    DIFFICULTY_PRESETS: dict

    def generate(self, seed: int, difficulty: dict) -> dict: ...
    def make_env(self, instance: dict) -> Env: ...
    def run_policy(self, instance: dict, policy: Policy) -> object: ...
    def verify(self, instance: dict, submission: object) -> RewardBreakdown: ...
    def ablate(self, instance: dict) -> dict: ...
    def render_instruction(self, instance: dict) -> str: ...


def public(instance: dict) -> dict:
    """Return the agent-visible view of an instance: drop ``_``-prefixed keys."""
    return {k: v for k, v in instance.items() if not k.startswith("_")}
