# Multi-Agent Foundational-Capability RL Data Generation

**A method for turning an agentic task database into multi-agent RL tasks
without ever designing a reward** — and for measuring which of the tasks it
produces are worth training on. Instantiated here on
[Gaia2](https://github.com/facebookresearch/meta-agents-research-environments),
the benchmark that ships with Meta's Agents Research Environments, packaged in
[Harbor](https://www.harborframework.com) format.

**Start here:**
[`docs/iteration_three_abilities.md`](docs/iteration_three_abilities.md) — the
capability taxonomy consolidated to three trainable abilities, the substrate
admitted and mined, and the honesty penalty measured. The method itself is
[`skills/constraint-forged-multi-agent-tasks/SKILL.md`](skills/constraint-forged-multi-agent-tasks/SKILL.md),
which is the canonical statement and the one to read if you are repeating this on
a different substrate. For task families deliberately built from first
principles instead of inherited from a benchmark, use
[`skills/build-ground-up-multi-agent-tasks/SKILL.md`](skills/build-ground-up-multi-agent-tasks/SKILL.md);
it requires independent generator/reference/verifier implementations,
adversarial and mutation review, versioned audit evidence, and clean-room
one-command delivery. Polished reports are available in
[English](docs/multi_agent_rl_data_generation_en.tex) and
[Chinese](docs/multi_agent_rl_data_generation_zh.tex) LaTeX, compiled to
`output/pdf/` (build them with `bash scripts/build_report.sh`).

## The method in one paragraph

Multi-agent capability data has no free oracle: judging coordination means
simulating the other agents, and then **you** design the reward — which is how
this repo's first attempt produced a `theory-of-mind` dimension that scored 1.0
on 12 of 12 runs while measuring instruction-following. (That reward was one line
of arithmetic, not a model. The lesson is about oracles nobody measured, not
about LLM judges.) Since no corpus of multi-agent traces with environments and
free oracles exists, **everyone has to manufacture the multi-agent structure. The
only question is which layer.** Design the judge and your mistakes become
invisible, because your own tests agree with your own errors. So this method
manufactures **only constraints** — which change *who can do what*, never *what
counts as done* — and takes the task, the ground truth, the environment and the
judge from a single-agent task database that already has them. A constraint's
failure mode is that the task gets too easy or too hard, and that is a thing you
can see.

> A badly chosen constraint makes a task too easy or too hard — **measurable**.
> A badly designed oracle makes the reward measure the wrong thing — **invisible**.
>
> Trade the invisible failure mode for the visible one.

## The four moves

Nothing here is Gaia2-shaped. The substrate is an argument to the method.

```
1. ADMIT      does the database qualify? four requirements, below
                          -> task, ground truth, environment, judge: all free
2. MINE       which tasks does the ground truth prove are multi-seam?
                          -> the roster comes from the task, never from you
3. CONSTRAIN  access / information / topology / budget
                          -> the multi-agent structure, and the ONLY thing built
4. ACCEPT     floor < score < control, per cell
                          -> which renders are usable RL data, measured
```

**Only move 3 is construction, and no knob in it can reach the judge.** The other
three are measurements — which is why the output is a *yield* rather than a
promise. This is SWE-smith's leverage, generalised: its 128 repos → 50k tasks
came not from clever bug injection but from **never designing an oracle** — break
something that works, let the existing tests grade the repair. SWE-smith breaks
the world; **this method blinds the agent.** Its Fail-to-Pass acceptance rule
generalises too: a graded oracle turns the flip into a sandwich (move 4).

### 1. ADMIT — what the method needs from a substrate

| requirement | why, and what breaks without it |
|---|---|
| **a verifier you did not write** | free, and already validated by somebody else — that is the whole of its value. Without it you are designing the oracle again |
| **real, executable, installable** | not a description of a world. If you cannot `pip install` or `docker pull` it, you will end up building it |
| **ground truth per task** | derives the roster *and* proves solvability. Without it you guess which tasks qualify, so you pad |
| **seams** | an action surface that divides along role boundaries — apps, services, repos, teams. No seams, no partition |

**Admission is necessary, not sufficient:** a database can ship a perfect oracle
and still have every task collapse into one seam. That is measured (move 2), not
assumed. `SKILL.md` carries the survey of what else clears the bar — SWE-smith,
τ-bench, R2E-Gym — and the disqualifiers, in the order they bite.

**How far this generalises, stated plainly:** the survey is a survey, not a set
of results. The reach claimed is the admission test's, not a measured one: *any
database clearing all four requirements should work.* Running the method on a
further substrate is the cheapest way to falsify that.

## The instantiation: Gaia2

Gaia2 clears all four: scenarios published in per-capability splits, a
write-action verifier with a scripted mode that has **no LLM in it**, an
installable harness (`are.simulation`), and apps that divide cleanly along role
boundaries. It was built explicitly for RL with verifiable rewards, and it is
hard. Every count below is one this repo measured on the splits it fetched, not
a figure quoted from the benchmark.

Ground truth is **gold write actions plus full initial app state**, not reference
code, so both mining rules port with new mechanics:

* **roster** = the apps the gold writes touch **plus** any app a seam proves was
  read (reads never appear in oracle events);
* **seam** = *state provenance*: a written argument value that exists in a
  different app's initial state, is absent from the target app's own state, and
  was not in the user instruction. The fact had to cross.

The constraint added: the Main gets **zero app tools** and can only delegate to
app-specialist sub-agents, each bound to one app and blind to the task.

| | source | designed here? |
|---|---|---|
| task, ground truth, oracle, environment | Gaia2 | **no** |
| access / information / topology / budget constraints | this repo | yes — and none of them can reach the judge |

### Move 2, measured: which scenarios can carry a partition

| split | scenarios | usable (roster ≥ 2) | seamful (a fact provably crosses) |
|---|---|---|---|
| `mini` | 160 | **111 (69%)** | **17 (11%)** |
| `adaptability` | 160 | **158 (99%)** | **30 (19%)** |

`sweep/gaia2_mini_admission.json`, `sweep/gaia2_adaptability_admission.json`.
The two sets overlap on 10 scenarios, so the corpus holds **37 unique seamful
scenarios → 148 rendered cells**, rosters 2–7, gold writes 5–16, DAG depth 1–4,
parallel width up to 12. The densest seam edges are Contacts→Cabs,
InternalContacts→Cabs and RentAFlat→Cabs, which suggests the provenance rule is
finding a real structural property of the apps rather than noise.

Per category in `mini`: adaptability 10/32 seamful, time 4/32, execution 3/32,
ambiguity 0/32, search 0/32. The zero rows are expected, not alarming — search
and ambiguity scenarios are read-heavy, Gaia2 verifies writes only, and a fact
that ends in the *answer* rather than in a write is invisible to state
provenance. The heuristic **under-reports by construction**: exact string match,
so a date reformatted in transit is invisible; values under 8 characters are
ignored; values present in 3+ apps are treated as ambient.

## The headline: what the instantiation measured

What follows prices *this substrate's knobs*, not the method — move 4 running on
move 3's output. The least flattering number here is the method's verdict on its
own tasks, and it is the one to read first.

All 37 seamful scenarios under the four-cell grid: **148 rollouts, one seed**,
Main and specialists both `gpt-5.6-sol`. `sweep/gaia2_full_campaign.json`.

| cell | knob turned | cells | successes | mean partial |
|---|---|---|---|---|
| `control` — `open-docs-binf` | none: one agent, every app | 37 | 2 | 0.251 |
| `discovery` — `star-names-binf` | visibility = names | 37 | 3 | 0.247 |
| `context` — `star-docs-binf` | the partition itself | 37 | 2 | 0.253 |
| `economy` — `star-docs-bN` | soft `bN` delegation target | 37 | 2 | 0.282 |

**No knob has been shown to bite, and the reason is the control.** The four means
sit within 0.035 of each other, and success is 2–3 of 37 everywhere including the
unconstrained arm. By this repo's own acceptance rule that is not a low yield —
it is **no yield at all**, because the rule refuses to read a constrained score
against a control that already failed. A control near the floor cannot price a
knob stacked on top of it; that is precisely the path by which a harness fault
gets published as difficulty, and the rule exists to catch it.

**Two more things the campaign is not.** It is **one seed** —
`SEEDS_FOR_YIELD = 5`, and the evidence file says so in its own note: *the first
pass of the five-seed sweep, not the sweep*. And the judge is confounded with the
scenario population: reply-conditioned scenarios are soft-judged and
unconditioned ones script-judged, which is **128 cells to `gpt-5.6-sol` (0
successes) and 20 to the scripted verifier (9 successes)**. The gap between those
two columns prices the judge and the scenarios together. It is not evidence about
either one alone.

**The soft judge's zero was a parse defect, not a verdict.** Measured
2026-08-31 by calling Gaia2's own soft checkers directly on the v6 rejections:
the checker model answers `Evaluation: [[true]]`, lowercase; the judge reads its
answer with `"[[True]]" in response`, case-sensitively; no sentinel matches, the
checker returns None, and `SoftToolJudge.compare` records that None as a
rejection. The model said pass and the judge wrote fail. Of 30 distinct v6
rejections replayed, 24 were this; the soft judge's 0 of 492 across five
campaigns is this. Replaying the same 30 with nothing changed but the case of
the match, **3 of 30 pass under the stock parse and 26 of 30 pass under the
fix** -- 23 abstentions were `[[true]]`, one was `[[false]]`, and the four that
still fail are four checkers that actually said no
(`sweep/gaia2_v6_judge_parse.json`). `forge/gaia2/judge_parse.py` reads the sentinel without
regard to case and changes nothing else -- not the oracle, the matching, the
hard checks, the checker prompts, or any verdict a checker gave. It is the one
modification this repo makes to the benchmark's judge; every trajectory stamps
`judge_parse` so no rollout graded before it can be read against one graded
after it. Every Gaia2 soft-judge number above predates the fix and is not a
statement about the agent.

**Where the episodes actually die** is the useful signal so far, and it is
diagnostic rather than about coordination (`sweep/gaia2_credit.json` stamps a
pivot on every row):

| pivot | rollouts | |
|---|---|---|
| `wrong-arguments` | 45 | the call was made, the arguments did not match gold |
| `malformed` | 40 | the model's tool-call syntax never parsed |
| `environment-stop` | 33 | the world ended the episode first |
| `refusal` | 11 | the specialist declined |
| `surrender` | 9 | the Main used the FAIL verb |
| `false-outage` | 7 | the specialist reported a tool broken that was not |

Forty malformed calls and 33 environment stops are 49% of the corpus dying
before coordination is on trial. Fixing those is the next measurement, not a
bigger grid.

**What this is:** a method, plus one substrate carried end to end — a working
forge, rendered Harbor tasks, 148 judged cells, and an honest and unfinished
measurement.

**On "good quality", which is the claim to be careful about.** The method does
not promise good tasks. It promises tasks whose quality is **decidable**, and
this campaign is that promise being kept in the direction nobody enjoys: the
acceptance rule looked at 148 cells and declined to certify any of them. A forge
without move 4 cannot tell a task that teaches coordination from one that is
unsolvable, one that is trivial, or one whose harness is broken; all four print a
number, and v1 shipped a dimension at reward 1.0 on 12 of 12 runs because nothing
here was watching. The yield is an output. Quality is measured, never asserted —
including when the measurement says *not yet*.

**What it is not:** a demonstrated curriculum, and not a priced knob. The
partition's cost on this substrate is **unmeasured**, because the control has not
yet cleared the floor. The next run is a control that succeeds, not more cells.

## Layout

| | |
|---|---|
| `forge/gaia2/` | the pipeline: `mine` (rosters and seams from gold write actions via state provenance) · `structure` (DAG depth, width, delegation targets) · `render` (constraint cells, one knob each) · `runtime` (Main + specialists with the WAIT verb Gaia2's simulated clock requires) · `credit` (partial credit and pivot annotation) · `are_world` (adapter over the official harness; needs `.venv-gaia2`, see below) · `harbor` + `cli` (packaging) |
| `forge/abilities.py` | the three trainable abilities (discovery, context transfer, delegation economy), each pinned to one constraint knob; yield per ability |
| `forge/models.py` | model classes and the parity rule: a specialist below the Main's model class refuses to run, in the sweep and in the shipped sidecar alike; overridable only by an explicit flag (`--allow-sub-downgrade`, or `MAF_ALLOW_SUB_DOWNGRADE=1` in a task's compose) so a downgrade is always a labelled experiment |
| `trajectory_viewer.html` | single-page viewer — one file, no server; carries an index of every episode, every task with its Harbor runs, every evidence file, and the current campaign's transcripts; files can be dropped on it or picked; the producers refresh it |
| `forge/maf/` | the earlier from-scratch forge; `parallel-scheduling` ships, two dimensions are quarantined (below) |
| `tasks/` | rendered Harbor tasks |
| `sweep/` | measurement evidence — one file per claim |
| `scripts/` | the probes that produced it |
| `skills/` | **the method** — canonical, substrate-independent, and the failure modes it was built from |

### Porting this to another substrate

`forge/gaia2/` is one instantiation, and it is worth knowing which files carry
the method and which are Gaia2 glue, because only the second column is thrown
away:

| file | ports? |
|---|---|
| `forge/abilities.py` | **the method.** One ability = one knob, and the yield bucketing on top of it. Needs a config name and a verdict, nothing Gaia2 |
| the acceptance rule | **the method.** Floor, control, sandwich, yield. Needs only a score, a floor and a control |
| `render.py` | **the method.** The four constraint families, none of which can reach a judge |
| `mine.py` · `structure.py` | **the rule ports, the mechanics do not.** "The roster is what the ground truth touches" is substrate-independent; state provenance over gold write arguments is Gaia2's particular way of showing it. So is the strict filter — every substrate has infrastructure that masquerades as a collaborator |
| `runtime.py` · `are_world.py` · `container/` | **glue.** Main + specialists, the WAIT verb, the sidecar boundary. Reimplemented per substrate |
| `credit.py` · `harbor.py` · `cli.py` | **glue.** Partial credit, packaging, entry points |

Every number above names the file that produced it:

| evidence | question |
|---|---|
| `gaia2_mini_admission.json` | Gaia2 mini: 111/160 multi-app, 17/160 with a provable cross-app fact |
| `gaia2_adaptability_admission.json` | the full adaptability split: 158/160 multi-app, 30/160 seamful |
| `gaia2_cells.json` | the rendered mini grid: 68 cells over 17 scenarios, rosters 3–7, writes 5–16, depth 2–4 |
| `gaia2_cells_adaptability.json` | 120 more cells; 37 unique seamful scenarios and 148 cells across both splits |
| `gaia2_first_episodes.json` | the first judged episodes, across three campaigns |
| `gaia2_full_campaign.json` | the four-cell grid over all 37 seamful scenarios, one seed |
| `gaia2_credit.json` | partial credit and pivot annotations over the same trajectories — deterministic, judge-free |
| `tom_degeneracy.json` | v1's `theory-of-mind`: 12 of 12 runs at reward 1.0, zero gradient |

## Setup

```bash
uv sync --locked                 # runtime + pytest, Ruff, and Pyright
cp .env.example .env             # then put your OPENAI_API_KEY in it
uv tool install 'harbor==0.18.0' # runs the tasks; not a project dependency
```

Harbor is a **tool**, not a library dependency: nothing in `forge/` imports it,
and it is deliberately absent from `pyproject.toml`. Every `harbor run` below
needs it, and needs **Docker running**.

The official Gaia2 harness (Meta's Agents Research Environments, import name
`are.simulation`) needs pydantic 2, which the main environment does not pin, so
it lives in its own virtualenv, installed from its own lock file:

```bash
uv venv .venv-gaia2 --python 3.11
uv pip sync --python .venv-gaia2/bin/python requirements-gaia2.txt
```

`requirements-gaia2.txt` is compiled from `requirements-gaia2.in` and pins all
95 transitive versions, not just the two packages worth naming. Its header
carries the command that rebuilds it, `--exclude-newer` and all — that cutoff is
the resolution the committed campaign actually ran under, so a recompile
reproduces the environment the episodes were measured in instead of quietly
resolving forward. `uv pip sync` rather than `install`: it removes anything the
file does not declare, which is what makes the guard in
`forge/tests/test_environment.py` able to insist the environment on disk matches.

The same file builds the Harbor sidecar. `forge/gaia2/container/Dockerfile.sidecar`
installs `-r requirements.txt`, and the renderer ships this exact file into every
task as that `requirements.txt` — so the environment you sweep in and the one a
reviewer's container runs are one list, not two that agree until they don't.

**Anything that touches `are.simulation` runs under `.venv-gaia2`, never the main
`.venv`.** That covers `gaia2_cell_run`, `gaia2_campaign`, and the Harbor sidecar.
Static analysis — fetching, admission, rendering — runs under the main `.venv`.
Address it by path (`--python .venv-gaia2/bin/python`) rather than by exporting
`VIRTUAL_ENV`: an exported one silently retargets every later `uv pip` in the
shell, including ones meant for the main environment.

```bash
uv run pytest
uv run ruff check forge scripts
uv run pyright
```

Building the optional PDFs also requires `latexmk` and XeLaTeX on `PATH`
(MacTeX supplies both on macOS); run `bash scripts/build_report.sh` after those
system tools are installed.

## Quickstart

**Fetch the splits, then measure and render** — no models involved, minutes on a
laptop:

```bash
set -a && . ./.env && set +a                          # OPENAI_API_KEY

uv run --with pandas --with pyarrow python -m scripts.gaia2_fetch   # --split adaptability etc.
uv run python -m scripts.gaia2_admission_probe       # which scenarios carry a partition? (no LLM)
uv run python -m scripts.gaia2_render_probe          # the ability grid, priced            (no LLM)
```

**Run one cell** and watch an episode happen — every message, delegation, tool
call and wait:

```bash
.venv-gaia2/bin/python -m scripts.gaia2_cell_run \
    --scenario gaia2_data/mini/scenario_universe_30_68r6vs.json \
    --ability control            # or capability-discovery / context-transfer / delegation-economy
```

For `delegation-economy`, `bN` is an efficiency target, not a hard cap. By
default `N` comes from the scenario's causal write/read structure; override it
for an experiment with `--economy-target 5`. Delegations beyond the target are
still allowed and only lower the completion-gated auxiliary economy reward.

Each run writes a full trajectory to `output/rollouts/`, judged by Gaia2's own
write-action verifier (scripted by default; `--judge-model` runs the official
soft judge). Open `trajectory_viewer.html`: it carries its own snapshot -- an
index of every episode ever run, with verdict, judge, parse, stop facts and
shaping signals; every task under `tasks/` with its Harbor runs linked; and
the full transcripts of the current campaign -- and the campaign, summary and
credit commands below refresh that snapshot themselves when they finish.
Older campaigns' transcripts open through the page's **open files** picker.
To refresh without a run: `uv run python -m scripts.embed_logs` (or
`--label v6` for a chosen campaign).

**The campaign** — the whole grid, then the two evidence files over it:

```bash
.venv-gaia2/bin/python -m scripts.gaia2_campaign --label full --workers 3
uv run python -m scripts.gaia2_campaign_summary --label full    # -> sweep/gaia2_full_campaign.json
uv run python -m scripts.gaia2_credit_probe     --label full    # -> sweep/gaia2_credit.json
```

`gaia2_credit_probe` calls no model: it recomputes coverage, fidelity and the
pivot from the trajectories on disk, so it is the one evidence file no judge can
move.

**Render Harbor tasks:**

```bash
uv run python -m forge.gaia2.cli render --scenario gaia2_data/mini/scenario_universe_30_68r6vs.json
```

A rendered Gaia2 task carries its whole world in `environment/scenario.json`, so
it rebuilds identically from its own directory — no dataset download, no install
step at run time.

**In containers** (the real deliverable — Docker required):

```bash
harbor run --path tasks/gaia2-star-docs-binf-scenario_universe_30_68r6vs \
    --agent terminus-2 --model openai/gpt-5.6-sol -n 1 --env-file .env
```

Read the result — `breakdown.json` is the interesting one, not `reward.txt`:

```bash
uv run python -m json.tool jobs/mine/*/gaia2-*/verifier/breakdown.json
```

| field | what it tells you |
|---|---|
| `partial` | the score. **Compare to the control before anything else.** |
| `failed` | *which* gold write actions were missed, by name |
| `ledger[].brief` | what the Main actually said to each specialist |
| `ledger[].report` | what came back — **read this first when a number looks wrong** |
| `ledger[].blocked_reasons` | the sandbox refusing something, and why |

### The execution contract

Every Gaia2 agent follows the versioned `objective-actions-v1` execution
contract: conditional writes wait for an observed trigger, creation establishes
the monitoring baseline, later transitions are updates, and each distinct
obligation or trigger receives exactly one successful side effect. Compatible
overlapping instructions use one write unless the user explicitly requires
separate actions. New trajectories record the contract version so they are not
silently compared with earlier prompt conditions.

This contract does not rewrite Gaia2's task or its verifier. It makes the
policy's interpretation explicit, which is a different experimental condition and
is therefore versioned rather than slipped in.

The earlier dimension still ships:

```bash
harbor run --path tasks/parallel-scheduling-0003 --agent oracle -n 1   # reward 1.0
```

## Two dimensions are quarantined, on purpose

`theory-of-mind` and `failure-recovery` are pinned as **failing their selfcheck
gate** — `xfail(strict=True)` on `test_selfcheck_passes` in
`forge/tests/test_theory_of_mind.py` and `forge/tests/test_failure_recovery.py`.
The gate they fail is V4, dictation-cheater: each instruction states its own
optimal algorithm, so following it literally *is* optimal play.

Their reward is the opposite of zero, and that is the point —
`test_theory_of_mind.py` asserts the oracle scores **1.0**. Reward 1.0 everywhere
is zero variance, zero advantage, **zero gradient**. They are kept, not deleted,
because the argument this repo is built on rests on them: they are what a green
dashboard looks like when it is measuring nothing.

## Tests

```bash
uv run pytest
uv run ruff check forge scripts
uv run pyright
```

The two xfails are deliberate: the quarantined dimensions failing their gate — the
gate working, not a defect.

---

`WRITEUP.md` is the engineering log. It was written against the previous
substrate and has not been migrated to Gaia2; read it for the failure modes, not
for the numbers.
