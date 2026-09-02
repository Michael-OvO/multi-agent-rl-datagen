---
status: idea
proposed: 2026-08-09T11:00:00-07:00
session: 3a1f0000-0000-4000-8000-0000000000a1
---
# Timezone handoff

**Pitch.** A coordinator must hand work to a teammate whose working hours have
already ended, and decide what to leave behind.

**Capability claim.** A coordinator can recognise when a delegation cannot be
answered before a deadline and pre-commit the fallback.

**Falsifiable counterfactual.** With all teammates always available, the same
models solve it at high rate.

**Why the current bank cannot measure this.** The Gaia2 scenarios have no
role-availability dimension at all.

**Sketch.** Two specialists with disjoint availability windows; the verifier
checks the fallback write exists when the primary path was unreachable.
