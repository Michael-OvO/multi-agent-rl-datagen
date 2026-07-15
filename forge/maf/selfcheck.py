"""The CLEAN/VALID gate battery (WRITEUP.md §1).

Run in-process at generation time — no Docker, no LLM tokens. An instance ships
only if every check passes. CLEAN = the reward has no noise; VALID = the reward
gap is caused by the target skill, and not by the instruction handing the agent
its own optimal algorithm (V4).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from forge.maf.core import transcript_hash

# Malformed submissions used to fuzz the verifier for C4.
_GARBAGE = [None, [], "garbage", 42, [{"subtask": "nope"}], {"x": 1}, [{}]]


@dataclass
class SelfcheckReport:
    ok: bool
    checks: dict = field(default_factory=dict)
    detail: dict = field(default_factory=dict)


def selfcheck(dim, instance, tau: float = 0.6, delta: float = 0.4,
              eps: float = 0.05) -> SelfcheckReport:
    checks: dict = {}
    detail: dict = {}

    # --- CLEAN -----------------------------------------------------------
    s1 = dim.run_policy(instance, dim.ORACLE)
    s2 = dim.run_policy(instance, dim.ORACLE)
    r_oracle = dim.verify(instance, s1)
    checks["C1_determinism"] = (
        transcript_hash(s1) == transcript_hash(s2)
        and r_oracle.reward == dim.verify(instance, s2).reward
    )
    checks["C2_solvable_fair"] = r_oracle.reward == 1.0
    detail["oracle_reward"] = r_oracle.reward

    ugt = getattr(dim, "unique_ground_truth", None)
    checks["C3_unique"] = bool(ugt(instance)) if ugt else True

    robust = True
    for g in _GARBAGE:
        try:
            rb = dim.verify(instance, g)
            if not (0.0 <= rb.reward <= 1.0):
                robust = False
        except Exception:
            robust = False
    checks["C4_verifier_robust"] = robust

    try:
        checks["C5_wellposed"] = dim.verify(instance, []).gate == 0
    except Exception:
        checks["C5_wellposed"] = False

    # --- VALID -----------------------------------------------------------
    cheater_rewards = {
        name: dim.verify(instance, dim.run_policy(instance, pol)).reward
        for name, pol in dim.CHEATERS.items()
    }
    detail["cheater_rewards"] = cheater_rewards
    checks["V1_cheaters_lose"] = all(v < tau for v in cheater_rewards.values())

    max_cheat = max(cheater_rewards.values(), default=0.0)
    checks["V2_discrimination"] = (r_oracle.reward - max_cheat) > delta

    twin = dim.ablate(instance)
    twin_rewards = [
        dim.verify(twin, dim.run_policy(twin, pol)).reward
        for pol in dim.CHEATERS.values()
    ]
    detail["twin_rewards"] = twin_rewards
    checks["V3_ablation"] = any(r >= 1.0 - eps for r in twin_rewards)

    # V4: the dimension must name which cheater is the best policy achievable by
    # mechanically executing its instruction text. V1 then requires that cheater
    # to score below tau. A dimension whose instruction states its own optimal
    # algorithm measures instruction-following, not the target skill --
    # theory-of-mind scored asks == q_opt on 12/12 sweep runs for exactly that
    # reason, and no cheater in its panel tested for it.
    dictation = getattr(dim, "DICTATION_CHEATER", None)
    checks["V4_dictation_declared"] = dictation in dim.CHEATERS
    detail["dictation_cheater"] = dictation

    return SelfcheckReport(ok=all(checks.values()), checks=checks, detail=detail)
