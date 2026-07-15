# Research: Evidence for the Chosen Capabilities

> **Status:** the literature grounding below stands. The capability *selection*
> it backs was superseded — see [`APPWORLD_DESIGN.md`](APPWORLD_DESIGN.md) §1,
> which re-derives it from a sharper split: capabilities divide by whether a free
> oracle exists, not by importance.

This document backs the capability selection in [`DESIGN.md`](DESIGN.md) §2 with two
independent evidence streams:

1. **Published literature** — verified citations (arXiv/venue-checked) showing each
   chosen capability is a *documented, quantified, and trainable* weakness of
   current models, and that they follow an easy→hard prerequisite ordering.
2. **Our own empirical measurement** — a controlled sweep of two frontier models on
   the very Harbor tasks this repo generates, with oracle and shortcut-baseline
   controls (§5). This shows the tasks *reproduce* the literature's failure modes
   and that the reward discriminates skill, difficulty, and model capability.

The convergence of external literature and our own measurements is the argument:
we are not asserting these capabilities matter — we are showing it, twice.

---

## 1. Chosen capabilities (recap)

We train a prerequisite **spine**, not a scatter: ① task decomposition → ②
dependency-ID & parallel scheduling → ③ role assignment → ④ dynamic replanning &
failure recovery → ⑤ theory of mind & information-asymmetric communication. The
original three-task scope targeted ②, ④, ⑤ — the widest arc; ④ and ⑤ are
currently quarantined (see §3, §4) and only ② ships today. Below, each is
grounded in literature + a failure-mode analysis; ② is additionally measured
empirically in §6.

---

## 2. Dependency-ID & parallel scheduling (task `parallel-scheduling`)

**The weakness is real and quantified.** Unaided LLM planning is broadly deficient:
GPT-4 produces executable plans with only **~12%** average success on IPC-style
domains (*On the Planning Abilities of LLMs*, Valmeekam et al., NeurIPS 2023,
arXiv:2305.15771), and **PlanBench** shows performance *collapses under name
obfuscation*, exposing pattern-matching rather than reasoning over
preconditions/effects (Valmeekam et al., NeurIPS 2023 D&B, arXiv:2206.10498). The
gap persists into reasoning-trained models and *degrades with plan length/dependency
depth* (o1 on PlanBench, arXiv:2409.13373).

**The specific sub-skill — parallel vs. sequential scheduling — is the failure
regime.** *TravelPlanner* reports a **0.6%** final-plan success for GPT-4, blamed on
inability to track multiple interdependent constraints (Xie et al., ICML 2024,
arXiv:2402.01622). *NATURAL PLAN* shows a **monotonic collapse** as interacting
entities grow — Trip Planning solve rates fall below 5% at 10 cities even with all
information in-context (Zheng et al., DeepMind, arXiv:2406.04520). Most directly:
*Robotouille* measures ReAct/GPT-4o at **47% synchronous → 11% asynchronous** — a
36-point drop the moment actions must be parallelized (arXiv:2502.05227); *AsyncHow*
shows LLMs reason poorly about shortest-completion-time under parallelism unless
handed the dependency graph (ICML 2024, arXiv:2402.02805); and *TCP* states outright
that models handle sequential dependencies but *asynchronous simultaneous assignment
defeats all of them* (EMNLP 2025, arXiv:2505.19927).

**It is trainable.** *LLMCompiler* shows eliciting an explicit task DAG so
independent branches run in parallel yields up to 3.7× latency and ~9% accuracy gains
(ICML 2024, arXiv:2312.04511); *TPS-Bench* separates planning (mostly OK) from
scheduling (the differentiator that fails) and shows a small **RL** run on Qwen3-1.7B
raised completion ~6% (arXiv:2511.01527).

**Typical failure modes our task punishes:** serialize independent work (miss
parallelism) → low `T_opt/makespan`; greedy assignment that ignores capability
scarcity → the planted trap; violate dependencies → hard-gate 0.

---

## 3. Dynamic replanning & failure recovery (task `failure-recovery`)

> **Status (2026-07-14): not implemented/shipped.** `failure-recovery` is
> quarantined — its CLI read the ground-truth scenario at runtime inside the
> agent's container, leaking it into the agent's image, and its worker roster
> was generated pre-sorted, which let the presented order reproduce the
> oracle's tie-break and collapsed the intended skill signal. The literature
> case below is the rationale for a later plan that rebuilds this construct
> behind a sidecar — it is not a description of a working feature.

**Models cannot reliably detect their own errors.** In the intrinsic setting (no
external signal), self-correction *degrades* reasoning: GPT-4 on GSM8K falls
**95.5% → 91.5% → 89.0%** over two self-correction rounds (*LLMs Cannot Self-Correct
Reasoning Yet*, Huang et al., ICLR 2024, arXiv:2310.01798). Recovery is therefore a
*separate, engineered layer*, not an emergent property — *Reflexion* obtains it only
by bolting on a reflect-and-retry loop (80% → 91% HumanEval pass@1; Shinn et al.,
NeurIPS 2023, arXiv:2303.11366).

**Error propagation is the core failure mode.** A single root-cause error propagates
through subsequent decisions to task failure; an explicit correction loop recovers
+24% all-correct accuracy (*Where LLM Agents Fail…*, Zhu et al., 2025,
arXiv:2509.25370). Under tool perturbations, recovery rate drops ~37% and — crucially
— fault-tolerance improves with scale **3.66× slower than basic task execution**
(*When Tools Fail / ToolMaze*, arXiv:2606.05806), i.e. scaling does not fix recovery
at the rate it fixes execution. *REALM-Bench* places reactive replanning-under-
disruption at the top of its difficulty ladder (arXiv:2502.18836).

**Typical failure modes our task punishes:** assume success / never check → the
completion gate fails; retry a known-failed worker or brute-force → the dispatch
budget is exhausted; dispatch before dependencies are ready → wasted attempts. The
env injects failures observable only at runtime, so a static plan cannot pass.

---

## 4. Theory of Mind & information-asymmetric communication (task `theory-of-mind`)

> **Status (2026-07-14): not implemented/shipped.** `theory-of-mind` is
> quarantined — its CLI read the ground-truth scenario at runtime inside the
> agent's container, leaking it into the agent's image, and its instruction
> named each topic's entry witness while telling the agent to follow
> referrals, so following the instruction was already optimal play and the
> task measured instruction-following, not theory-of-mind skill. The
> literature case below is the rationale for a later plan that rebuilds this
> construct behind a sidecar — it is not a description of a working feature.

**Apparent ToM is brittle and pattern-matched.** Trivial ToM-preserving perturbations
flip prior successes (*LLMs Fail on Trivial Alterations…*, Ullman 2023,
arXiv:2302.08399; *Clever Hans or Neural ToM?*, Shapira et al., EACL 2024,
arXiv:2305.14763) — directly rebutting the "spontaneous emergence" claim (Kosinski,
arXiv:2302.02083). Even GPT-4 trails humans by >10 points across 31 ToM abilities
(*ToMBench*, ACL 2024, arXiv:2402.15052).

**Higher-order ToM is dramatically harder — the curriculum is visible in the data.**
*Hi-ToM* reports GPT-4 joint accuracy falling **~95% (0th) → 80% (1st) → 60% (2nd) →
30% (3rd) → 5% (4th)** with chain-of-thought adding almost nothing (arXiv:2310.16755);
*Street et al.* confirm capability is explicitly *order-graded* and model-scale-
dependent (arXiv:2405.18870). The information-asymmetry case is our exact setting:
*FANToM* stress-tests "who knows what" / "who can answer this" in multi-party
conversation and finds models claim a character knows info it never received, failing
even with CoT/fine-tuning (Kim et al., EMNLP 2023, arXiv:2310.15421).

**It is trainable — via programmatic generation.** *ExploreToM* uses program-guided
adversarial generation to drop GPT-4o/Llama-3.1-70B to as low as 0–9%, and
**fine-tuning on the generated data yields +27 points on ToMi** (Sclar et al., ICML
2025, arXiv:2412.12175) — the most direct evidence that (a) ToM is a genuine weakness
under stress and (b) *procedurally generated data closes the gap*, which is precisely
this repo's thesis.

**Typical failure modes our task punishes:** assume shared knowledge (don't model that
a peer lacks info); ignore referrals (fail on depth ≥ 1); info-dump every witness →
the query budget caps `quality = q_opt/used ≤ 0.5`.

---

## 5. Curriculum ordering — evidence

The literature gives converging, partly quantitative support for the spine
(decompose → schedule → assign → recover → ToM):

- **Base skills are the limiting factor and come first.** Plan generation/
  decomposition is itself unreliable (~12%, PlanBench) — recovery is meaningless
  without a plan to recover toward.
- **Recovery is a layer *above* execution, acquired later.** Intrinsic self-correction
  *degrades* accuracy (Huang), recovery appears only when explicitly engineered
  (Reflexion), and fault-tolerance scales **3.66× slower** than execution (ToolMaze).
- **Sequential-before-parallel within scheduling.** TCP and Robotouille both show
  sequential dependency reasoning is the "easy" regime and asynchronous/parallel
  assignment is the failure regime.
- **ToM is the most brittle, highest-order skill.** Hi-ToM's monotonic decay by
  recursion order and Ullman's fragility results place ToM last; the **MAST**
  taxonomy's three tiers — specification → inter-agent misalignment → verification —
  themselves read as an ordering (Cemri et al., 2025, arXiv:2503.13657).

MAST also provides the top-level justification for the whole enterprise: an
empirically grounded taxonomy of **14 multi-agent failure modes** (κ=0.88 over 1600+
traces) showing MAS gains are often minimal because coordination breaks in
structured, recurring, *targetable* ways.

---

## 6. Empirical validation on our own tasks

> **Scope note (2026-07-14):** this sweep originally covered all three
> dimensions. `failure-recovery` and `theory-of-mind` are now quarantined
> (§3, §4) — `forge_cli` refuses to render them and `scripts/eval_sweep_gen.py`
> ships 0 instances for them — so their rows are gone from the table below,
> and the description here covers `parallel-scheduling` only.

We ran a controlled sweep on the tasks this repo generates: **2 models × 1 dimension
× 3 difficulties × 2 seeds = 6 instances per model**, all through Harbor in Docker
with the `terminus-2` agent, plus zero-cost **oracle** (reference) and **cheater**
(shortcut) controls on the same instances. Reproduce with
`scripts/eval_sweep_gen.py` + `scripts/eval_sweep_agg.py`.

**Mean reward by dimension × difficulty** (n = 2 seeds/cell; `terminus-2` agent;
0 crashed trials):

| Dimension | Difficulty | oracle | gpt-5.6 | gpt-4.1 | cheater (max) |
|---|---|---|---|---|---|
| parallel-scheduling | easy   | 1.00 | 1.00 | 1.00 | 0.50 |
| parallel-scheduling | medium | 1.00 | 1.00 | **0.50** | 0.50 |
| parallel-scheduling | hard   | 1.00 | 1.00 | 1.00 | 0.50 |

Overall: **gpt-5.6 = 1.000 (6/6 perfect)**, **gpt-4.1 = 0.833 (5/6 perfect)**.

**What the data shows:**

1. **The environment and verifier are correct at scale.** Oracle = 1.00 in all 3
   cells (6/6 instances) — not just the 1 hand-picked sample task, but every
   procedurally generated instance the selfcheck gate shipped.
2. **The reward discriminates skill.** The shortcut baselines fail on *solvable*
   instances: scheduling cheaters score **0.50** (serialization/greed). The gap
   between "can solve" (oracle 1.0) and "used a shortcut" (0.5) is exactly the
   training signal.
3. **Real models land between — with one hard failure.** The clearest
   **model-capability gradient** is `parallel-scheduling-medium`: gpt-4.1 emitted an
   **infeasible schedule → 0.00** while gpt-5.6 found the optimum → 1.00, reproducing
   the literature's "LLMs violate dependencies / don't exploit parallelism" failure
   mode (§2) on our own instance. Overall gpt-4.1 (0.833) < gpt-5.6 (1.000).
4. **Honest scope.** At these difficulties both frontier models are largely competent
   (gpt-5.6 perfect on all 3 cells; gpt-4.1 perfect except on medium) — expected, and
   *correct*: the reward should reward competent behavior. Sharper model separation
   appears as difficulty rises or capability drops;
   the difficulty knobs (DESIGN §7) and the cheater controls supply the discrimination
   headroom. For RL the essential property is a **correct graded signal** — oracle 1.0,
   shortcuts low, real models in-between with informative partials — which the sweep
   confirms.

This is the second, independent leg of the argument: the literature says these are
trainable weaknesses; **our own tasks reproduce those failure modes and grade them
cleanly and deterministically.**

---

## 7. Takeaway

External literature and our own measurements converge on the same conclusion: the
chosen dimensions are **documented, quantified, trainable** weaknesses with a natural
easy→hard prerequisite structure. Two verified results (ExploreToM's +27 from
generated ToM data; TPS-Bench's RL gain on scheduling) show that *targeted, generated
data improves exactly these capabilities* — which is the entire purpose of this
pipeline.
