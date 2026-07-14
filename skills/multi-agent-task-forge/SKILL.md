---
name: multi-agent-task-forge
description: Use when generating verifiable RL tasks that train multi-agent orchestration skills (task decomposition, parallel scheduling, failure recovery, theory-of-mind, role assignment) in Harbor format — provides the Dimension contract, the CLEAN/VALID gate battery, and a checklist for adding new capability dimensions at scale.
---

# Multi-Agent Task Forge

Generate deterministic, verifiable, construct-valid RL tasks for multi-agent
**orchestration** capabilities, packaged as Harbor tasks. Full rationale in
`docs/DESIGN.md`.

## The one idea

**Invert the multi-agent setup.** The model under test plays the single
**orchestrator (Main agent)** role; every other agent and the world are a
**deterministic scripted environment that holds ground truth**. The environment
*is* the verifier — so reward is programmatic, reproducible, and cheap.

Each capability = a **Dimension**: a parametric environment family that
`generate(seed, difficulty)` samples. `forge/` already ships three
(`parallel-scheduling`, `failure-recovery`, `theory-of-mind`).

## Non-negotiable invariants

1. **Constructive generation.** Plant the instance *and* its optimal solution
   together so the oracle *replays* — never *searches* — at grade time. If a
   quantity would need an NP-hard solve to grade, construct it so the optimum is
   known (e.g. scheduling makespan = critical-path length).
2. **Continuous reward** `= gate ∈ {0,1} × quality ∈ (0,1]`, written as a float
   to `/logs/verifier/reward.txt`. Oracle → 1.0.
3. **Public-interface fairness.** The oracle and every cheater act only through
   the same surface the agent uses (the artifact or the CLI). Never read `_`-
   prefixed ground-truth fields from a policy.
4. **Ship only if the CLEAN/VALID battery passes** (below). No human in the
   per-instance loop.

## The Dimension contract (`forge/maf/core.py`)

Implement a module in `forge/maf/dimensions/` exposing a `DIM` object with:

```
NAME, SUBMISSION_FILE, INTERACTIVE, GOAL, OUTPUT_CONTRACT, DIFFICULTY_PRESETS
CLI_NAME                         # interactive dims only ("coord" / "interview")
generate(seed, difficulty) -> instance dict   # ground truth under "_" keys
make_env(instance, state=None) -> Env         # interactive dims: state machine
run_policy(instance, policy) -> submission    # execute a policy -> graded artifact
verify(instance, submission) -> RewardBreakdown
ablate(instance) -> instance                  # the skill-removed twin
render_instruction(instance) -> str
unique_ground_truth(instance) -> bool         # optional (C3)
ORACLE, CHEATERS = {name: policy}
```

Interactive `Env` exposes `handle(argv) -> dict`, `state() -> dict`, and records
each interaction on `self.transcript`. The generic `runtime/cli.py` drives it in
the container; `runtime/verify_entry.py` grades it. Both are copied in verbatim.

## The CLEAN/VALID gate battery (`forge/maf/selfcheck.py`)

Run in-process at generation time (no Docker, no tokens). Ship iff **all** pass:

- **C1 Determinism** — oracle run twice → identical reward + transcript hash.
- **C2 Solvable & fair** — oracle reaches 1.0 through the public interface.
- **C3 Unique ground truth** — the graded optimum is well-defined.
- **C4 Verifier robustness** — malformed submissions → reward in [0,1], no crash.
- **C5 Well-posed** — an empty/format-only submission scores gate 0.
- **V1 Cheater panel** — each shortcut policy scores `< τ` (0.6).
- **V2 Discrimination** — `oracle − max(cheaters) > Δ` (0.4).
- **V3 Ablation twin** — a cheater that failed V1 scores `≥ 1−ε` on the twin,
  *proving the reward gap is caused by the target skill* (counterfactual).

## Checklist: add a new dimension

- [ ] Name the skill and the **shortcuts** a model could exploit to fake it.
- [ ] Design an environment where each shortcut provably loses (a cheater per
      shortcut) and the skill provably wins.
- [ ] Write `generate` **constructively** (plant instance + optimal solution).
- [ ] Implement `verify` as `gate × quality`; make it robust to garbage (C4).
- [ ] Write `ORACLE` (public interface only) and the `CHEATERS` panel.
- [ ] Write `ablate` so removing the skill-forcing mechanism lets a cheater win.
- [ ] Add tests mirroring `forge/tests/test_<dim>.py`; confirm `selfcheck` passes
      across ≥20 seeds.
- [ ] Register in `forge/forge_cli.py`; generate a batch and eyeball the
      shipped/rejected summary.

## Generate & verify

```bash
python -m forge.forge_cli gen --dim <name> --seed 0 --n 100 \
    --difficulty medium --out tasks/          # selfcheck-gated
python3 scripts/dryrun_local.py               # oracle=1.0, no Docker
bash scripts/verify_all.sh                     # real Harbor oracle run (Docker)
```

## Scale notes (see DESIGN §8)

`seeds` scale *volume/anti-memorization*, not *coverage*. Coverage scales by
**composing orthogonal primitives** (DAG × capabilities × failure-injection ×
info-partition × topology × adversary) into new dimensions, and depth scales by a
**policy-tracking curriculum**. The primitive library is the asset; instances are
free on top of it.
