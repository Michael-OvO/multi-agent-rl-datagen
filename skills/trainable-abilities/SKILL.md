---
name: trainable-abilities
description: The three multi-agent abilities worth rendering RL cells for — capability discovery, context transfer, delegation economy — and the one-knob rule that keeps each cell pricing exactly one of them. Use when choosing which constraint configurations to render on any substrate.
---

# The Three Trainable Abilities

Of everything a multi-agent Main must do, exactly three abilities sit at the
intersection of (a) the largest measured failure mass, (b) proven RL
trainability, and (c) verification the substrate's own oracle provides for
free. Render cells for these; treat everything else as either emergent or
not yet oracle-affordable.

| ability | sub-decision | evidence it matters | evidence it trains |
|---|---|---|---|
| **capability-discovery** | *whom* to delegate to | MAST inter-agent misalignment: 36.9% of 1,600+ annotated failures | ToolRL (NeurIPS 2025): GRPO on tool selection, +17%/+15%, emergent ask-first behaviour |
| **context-transfer** | *what* goes in the brief | MAST specification + misalignment ≈ 79%; Gaia2 A2A is every model's weakest category | SWEET-RL: turn-level credit on collaborative tasks works |
| **delegation-economy** | *when* to spawn / stop | MAST step repetition 15.7% + termination unawareness 12.4% | Uno-Orchestra (2026): Agentic-GRPO for selective delegation |

Why only these three: their failure is visible within one delegation round,
so the inherited outcome oracle grades them without a coordination judge —
and they are the orchestrator's entire set of high-consequence turns, which
is what GRPO-family training needs (signal-to-noise degrades as decision
density falls; arXiv 2606.22164). Theory of mind and failure recovery stay
quarantined: no free oracle exists, and building one is the invisible
failure mode this whole method exists to avoid.

## The one-knob rule

A cell prices an ability only if exactly one knob is turned; everything
else sits at its neutral setting:

```
capability-discovery   star + names + no budget    (only docs are missing)
context-transfer       star + docs  + no budget    (only the partition bites)
delegation-economy     star + docs  + budget=len(roster)  (only the budget bites)
```

`forge/abilities.py` is the enforcement: `config_for(ability, roster)`
renders these and nothing else; `ability_of(label)` tags sweep rows (finite
budget wins precedence, so a two-knob stray is priced once, never twice);
`yield_by_ability(cells)` reports usable-over-measurable per ability with
`validity`'s semantics unchanged.

## Per-substrate checklist

1. Mine rosters and seams — a data-flow pass over reference code on code
   substrates, `forge/gaia2/mine` state provenance on gold-write substrates.
2. Render the three configs per seamful task, plus the one shared control.
3. Establish the ceiling and the floor *before* reading any constrained cell.
   A control that has not cleared the floor makes every knob unpriceable, and
   the sandwich rule will correctly refuse to certify anything.
4. Sandwich-judge at ≥5 seeds; report yield per ability, not per config.
5. Run the honesty probe: any family where a truthful-failure agent scores
   below the do-nothing floor fails admission until the *protocol* (never the
   judge) is fixed.
