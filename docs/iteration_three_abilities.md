# Iteration 2 — the three abilities, a second substrate, and the price of honesty

**Date:** 2026-07-26. **Everything below is measured; every number names its
evidence file.** No LLM was involved in any measurement in this iteration —
all three are deterministic probes.

## What this iteration adds

1. **The three-abilities layer** (`forge/abilities.py`): the capability
   taxonomy consolidated to the three most trainable multi-agent abilities,
   each pinned to exactly one constraint knob so a rendered cell prices one
   ability and never a blend:

   | ability | sub-decision | knob turned | everything else |
   |---|---|---|---|
   | `capability-discovery` | *whom* to delegate to | visibility = names | docs off is the knob; budget off |
   | `context-transfer` | *what* to put in the brief | the partition itself | docs on, budget off |
   | `delegation-economy` | *when* to spawn / stop | task-derived soft `bN` target | docs on (discovery neutralised) |

   Selection criteria (external evidence, see WRITEUP-adjacent discussion):
   largest measured failure mass (MAST, NeurIPS 2025: specification +
   inter-agent misalignment ≈ 79% of 1,600+ annotated failures), proven RL
   trainability (ToolRL, NeurIPS 2025; Uno-Orchestra 2026), and short credit
   chains under the signal-dilution bound for GRPO-family training
   (arXiv 2606.22164). `ability_of` tags existing sweep rows;
   `yield_by_ability` buckets validity verdicts per ability.

2. **A second substrate, mined** (`forge/gaia2/`): Gaia2 (Meta ARE,
   ICLR 2026) — 1,120 scenarios, write-action verifiers, explicitly built
   for RL with verifiable rewards, and hard (GPT-5 high: 42% pass@1 —
   against AppWorld's measured 1.000 control). Ground truth is gold write
   actions plus full initial app state, not reference code, so both mining
   rules port with new mechanics:

   * **roster** = apps the gold writes touch **plus** apps a seam proves
     were read (reads never appear in oracle events);
   * **seam** = *state provenance*: a written argument value that exists in
     a different app's initial state, is absent from the target app's own
     state, and was not in the user instruction. The fact had to cross.

   Only the miner is built. The runtime, sandbox and Harbor packaging for
   ARE are future work — this iteration admits and measures, it does not
   yet render.

3. **The honest-failure probe** (`scripts/appworld_honesty_probe.py`): the
   scripted agent the up-scale plan calls for — it truthfully reports
   failure and measures what the protocol pays for that.

## Measured: Gaia2 mini admission (`sweep/gaia2_mini_admission.json`)

160 scenarios (the `mini` split, 32 per capability category):

| measure | count | rate |
|---|---|---|
| usable (roster ≥ 2) | **111 / 160** | 69% |
| seamful (a fact provably crosses apps) | **17 / 160** | 11% |

Per category: adaptability 10/32 seamful, time 4/32, execution 3/32,
ambiguity 0/32, search 0/32. The zero rows are expected, not alarming:
search and ambiguity scenarios are read-heavy — Gaia2 verifies writes only,
and a fact that ends in the *answer* rather than in a write is invisible to
state provenance. Densest seam edges: Contacts→Cabs (7),
InternalContacts→Cabs (7), RentAFlat→Cabs (5).

Read against AppWorld: the strict multi-app rate doubles (69% vs 35% =
51/147), and 17 seamful scenarios from one 160-scenario slice compares with
AppWorld's whole shipped family of 3 tasks. Extrapolated to the full 1,120
scenarios this is ~120 seamful candidates before any parameterisation — but
that is an extrapolation, not a measurement, and the seam heuristic
**under-reports by construction** (exact string match: a date reformatted in
transit is invisible; values shorter than 8 chars are ignored; values in 3+
apps are treated as ambient).

## Measured: the price of honesty (`sweep/appworld_honesty.json`)

Two scripted honest agents on all three shipped AppWorld tasks, against the
0.333 do-nothing floor (`sweep/appworld_donothing.json`):

| agent | behaviour | partial | vs floor |
|---|---|---|---|
| `honest-prose` | truthful failure report as the answer text | **0.167 on 3/3 tasks** | **below floor** |
| `honest-fail` | `complete_task(status='fail')` | **0.333 on 3/3 tasks** | at floor |

Two findings. First, the 0.167 trap WRITEUP.md §5 found in one star-names
cell is **systematic**: every shipped task pays an agent 1/6 more for a
false `completed` than for a truthful prose report. At RL scale that is a
training signal to lie. Second — new — **the protocol already contains a
zero-cost honest channel**: `status='fail'` scores exactly the floor. The
mitigation is not an oracle change (never touch the judge); it is a runtime
protocol note steering the Main to `status='fail'` over prose surrender,
plus this probe as the permanent regression test. Any future substrate or
task family where `honest-*` scores below the do-nothing floor fails
admission.

## Measured: the rendered grid (`sweep/gaia2_cells.json`)

The 17 seamful scenarios render into **68 cells** — the shared control plus
one cell per ability per scenario, the one-knob rule enforced by
construction (`forge/gaia2/render.py`). What the structure mining
(`forge/gaia2/structure.py`) says about them, against AppWorld's shipped
family:

| | AppWorld family (shipped) | Gaia2 seamful (rendered) |
|---|---|---|
| roster size | 2 | **3–7** (median 5–6) |
| gold writes / reference calls | short scripts | **5–16 writes** |
| forced sequencing (DAG depth) | shallow | **2–4** |
| parallel width | 2 | **2–12** |

These are longer-horizon, wider tasks: a star Main gets up to 12
parallelizable gold writes in one fan-out. The later runtime implementation
replaced the original roster-size hard budget with an adjustable,
causal-phase heuristic target: independent same-frontier actions regroup by
app, reply/wait barriers force a new visit, and alternative provenance
sources charge only one read. Exceeding `bN` never blocks completion; it
smoothly lowers a completion-gated auxiliary economy reward.

**The ability lens is wired into acceptance:** `cli judge` now reports
yield per ability on top of yield per config. Re-reading the committed v5
sweep through it: **capability-discovery 2/3 (67%), context-transfer 3/3
(100%), both at five seeds — measured YIELD** — and chain rows land in no
bucket, because a changed topology is a second turned knob
(`test_v5_sweep_ability_yield_matches_the_readme` pins this against the
evidence files).

## Built: the honest-failure channel (the trap, closed at the protocol layer)

The probe made the trap measurable; this round closes it where the method
allows — the protocol, never the judge. The Main's contract now includes a
surrender verb (`FAIL :: <reason>`, `forge/appworld/runtime.py`), `run_main`
returns it instead of nagging it as malformed, and one shared
`submission_code()` routes every surrender sentinel (`FAIL`, out-of-steps,
no-answer) through `complete_task(status='fail')` — the channel the honesty
probe prices at exactly the floor. All three submission sites (knob sweep,
sidecar server, watch_episode) now use it; error rows keep their prose so a
crash never masquerades as graceful failure. The committed Harbor tasks were
re-rendered so the shipped runtime is the measured runtime — the drift gate
(`test_committed_tasks_match_the_generator`) is what forced that, which is
the gate working. `forge/tests/test_honest_failure.py` pins the whole
channel.

**What this changes for RL data:** before, an honest Main was paid 1/6 less
than a lying one; now honesty and doing-nothing price identically, and the
oracle's side-effect checks still separate real work from claims. The lie
incentive is gone from every cell this forge renders going forward.

## Measured: the `adaptability` split (`sweep/gaia2_adaptability_admission.json`)

The full 160-scenario split behind mini's best category, fetched and mined:

| measure | mini (160) | adaptability (160) |
|---|---|---|
| usable (roster ≥ 2) | 111 (69%) | **158 (99%)** |
| seamful | 17 (11%) | **30 (19%)** |

Overlap with mini's seamful set: 10 scenarios, so the corpus now holds **37
unique seamful scenarios → 148 rendered cells**
(`sweep/gaia2_cells.json` + `sweep/gaia2_cells_adaptability.json`), rosters
2–7, writes 5–16, depth 1–4, width up to 12. Same dominant seam edges
(Contacts/InternalContacts → Cabs/Messages), which suggests the provenance
rule is finding a real structural property of the ARE apps, not noise. Four
splits remain unfetched (`ambiguity`, `execution`, `search`, `time` — the
full versions); `scripts/gaia2_fetch.py --split <name>` now takes any of
them.

## Objective action contract (`objective-actions-v1`)

Conditional language and repeated writes now have one literal execution
contract, shared byte-for-byte by the in-process Main, every specialist, and
the shipped Harbor instruction:

1. A conditional action becomes due only after its trigger is observed in a
   user message, environment notification, or tool result.
2. In monitoring tasks, creation or first observation establishes the
   baseline. “Update” and “change” mean a later observed transition unless the
   user explicitly includes the initial state.
3. Each distinct obligation or observed trigger gets exactly one successful
   side effect. Only an explicitly failed or rejected call may be retried.
4. One write may satisfy overlapping instructions. A second write that merely
   repeats the same fact is forbidden unless the user explicitly requires
   separate actions, recipients, times, or repetitions.
5. Before writing, the agent uses its transcript as a ledger: name the
   obligation or trigger, establish that it is due, and establish that no
   successful write already satisfied it.

This contract does not rewrite Gaia2's task or verifier. It makes the policy's
interpretation explicit and records its version in new trajectories, because a
prompt-policy change creates a different experimental condition. Conversely,
an inherited verifier's raw counter mismatch proves divergence from its oracle;
it does not by itself prove a semantic user-instruction violation. If the task
text still permits materially different side effects, that cell is ambiguous
and must be quarantined or human-adjudicated rather than used as a clean
negative training example.

## What this iteration does *not* claim

No Gaia2 cell has been rendered, rolled out, or judged — admission is
necessary, not sufficient, and the sandwich still decides everything. The
seam counts are a tested heuristic's output, not a dependency proof. And the
three-abilities layer re-tags existing evidence; it does not create new
rollouts. The next measurement is the expensive one: an ARE runtime and a
five-seed sweep of `config_for(ability, roster)` cells on the 17 seamful
scenarios, against Gaia2's own write-action verifier.

## Evidence

| file | question it answers |
|---|---|
| `sweep/gaia2_mini_admission.json` | which Gaia2 mini scenarios can carry a partition, and where the facts cross |
| `sweep/gaia2_cells.json` | the rendered mini grid: 68 ability-tagged cell specs with roster, seams, and DAG structure |
| `sweep/gaia2_adaptability_admission.json` | the full adaptability split: 158/160 multi-app, 30/160 seamful |
| `sweep/gaia2_cells_adaptability.json` | 120 more rendered cells from the adaptability split |
| `forge/tests/test_honest_failure.py` | the FAIL verb, the surrender predicate, and the status='fail' routing |
| `sweep/appworld_honesty.json` | what truthful failure costs, per task, per reporting channel |
| `forge/tests/test_abilities.py` | one ability = one knob; tagging precedence; yield bucketing |
| `forge/tests/test_gaia2_mine.py` | the provenance rules, including the two ways a value is *not* a seam |
