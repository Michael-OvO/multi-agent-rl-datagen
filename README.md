# Multi-Agent Foundational-Capability RL Data Generation

**A method for turning an agentic task database into multi-agent RL tasks
without ever designing a reward** — and for measuring which of the tasks it
produces are worth training on. Instantiated here on
[AppWorld](https://appworld.dev), packaged in
[Harbor](https://www.harborframework.com) format.

**Start here:** [`WRITEUP.md`](WRITEUP.md) — what was built, what was measured,
and what it turned out to measure. The method itself is
[`skills/constraint-forged-multi-agent-tasks/SKILL.md`](skills/constraint-forged-multi-agent-tasks/SKILL.md),
which is the canonical statement and the one to read if you are repeating this on
a different substrate. Polished reports are available in
[English](docs/multi_agent_rl_data_generation_en.tex) and
[Chinese](docs/multi_agent_rl_data_generation_zh.tex) LaTeX, compiled to
`output/pdf/` (build them with `bash scripts/build_report.sh`).

## The method in one paragraph

Multi-agent capability data has no free oracle: judging coordination means
simulating the other agents, and then **you** design the reward — which is how
this repo's first attempt produced a `theory-of-mind` dimension that scored 1.0
on 12 of 12 runs while measuring instruction-following. (That reward was one line
of arithmetic, not a model. The lesson is about oracles nobody measured, not
about LLM judges — see [`WRITEUP.md`](WRITEUP.md) §6.) Since no corpus of
multi-agent traces with environments and free oracles exists, **everyone has to
manufacture the multi-agent structure. The only question is which layer.** Design
the judge and your mistakes become invisible, because your own tests agree with
your own errors. So this method manufactures **only constraints** — which change
*who can do what*, never *what counts as done* — and takes the task, the ground
truth, the environment and the judge from a single-agent task database that
already has them. A constraint's failure mode is that the task gets too easy or
too hard, and that is a thing you can see.

> A badly chosen constraint makes a task too easy or too hard — **measurable**.
> A badly designed oracle makes the reward measure the wrong thing — **invisible**.
>
> Trade the invisible failure mode for the visible one.

## The four moves

Nothing here is AppWorld-shaped. The substrate is an argument to the method.

```
1. ADMIT      does the database qualify? four requirements, below
                          -> task, ground truth, environment, judge: all free
2. MINE       which tasks does the reference solution prove are multi-seam?
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
| **a reference solution per task** | derives the roster *and* proves solvability. Without it you guess which tasks qualify, so you pad |
| **seams** | an action surface that divides along role boundaries — apps, services, repos, teams. No seams, no partition |

**Admission is necessary, not sufficient:** a database can ship a perfect oracle
and still have every task collapse into one seam. That is measured (move 2), not
assumed. `SKILL.md` carries the survey of what else clears the bar — SWE-smith,
τ-bench, R2E-Gym — and the disqualifiers, in the order they bite.

**How far this generalises, stated plainly:** the survey is a survey, not a set
of results. **This method has been run end to end on exactly one substrate.** The
reach claimed is the admission test's, not a measured one: *any database clearing
all four requirements should work, and one has.* A second substrate is the
cheapest way to falsify that, and nobody has done it.

## The instantiation: AppWorld

AppWorld clears all four: 9 real apps, 457 APIs, 732 tasks, and a programmatic
state-based oracle with **no LLM in it** that also catches side effects. The
constraint added: the Main gets **zero APIs** and can only delegate to
app-specialist sub-agents, each bound to one app and blind to the task.

| | source | designed here? |
|---|---|---|
| task, ground truth, oracle, environment | AppWorld | **no** |
| access / information / topology / budget constraints | this repo | yes — and none of them can reach the judge |

## The headline: what the instantiation measured

What follows prices *this substrate's knobs*, not the method. Read it as move 4
running on move 3's output — and note that the method's verdict on its own
tasks is the least flattering number here.

Three tasks, **five seeds each** (15 rollouts per config), Main = gpt-5.6-sol,
specialists = gpt-4.1. `sweep/appworld_knobs_v5.json`. Do-nothing = 0.333.

| config | mean | |
|---|---|---|
| `open` — one agent, every API | **1.000** | the control, on 15 of 15 rollouts |
| `star-docs` — no APIs, reads its specialists' real API catalogs | **0.855** | the partition costs 0.145 |
| `star-names` — no APIs, does not know what they can do | **0.445** | but see below |
| `chain-names` | 0.250 | unshipped: the topology is unimplemented (2 seeds) |

**Taking a frontier model's tools away and making it delegate costs 0.145, and
the seeds are what made that sayable.** The control scored 1.000 on *every one*
of its 15 rollouts; `star-docs` landed below it on **10 of 15**, spread across
0.667–1.000. At one seed this table read 0.944 and the honest caveat was that
three tasks at one draw cannot separate 0.056 from noise. That caveat was
correct, and the fix was seeds, not a bigger claim.

**Do not read the `star-names` drop as the visibility knob.** One of its three
tasks scores **0.167 on all five replicates — below the do-nothing floor** —
because the Main honestly reported that it had found nothing, in prose, and
AppWorld's `assert answers match` expects the action-task answer (`None`).
Reporting failure costs 1/6 more than falsely claiming `completed`. That is a
reward-hacking incentive in the protocol, not a difficulty gradient
(`WRITEUP.md` §5), and five seeds do not launder it: it is the same 0.167 every
time.

This repo previously reported `1.000 → 0.333` for the partition. That number was a
truncated API catalog hiding the verb the task needed — the specialists could not
find `like_transaction`, so they could not act, so the Main scored the floor no
matter how well it coordinated. [`WRITEUP.md`](WRITEUP.md) §7 is that story;
the numbers above are the re-measurement.

**What this is:** a method, plus one substrate carried end to end — a working
forge, 6 rendered Harbor tasks, 3 with verified passing solutions, and an honest
and unfinished measurement.

**On "good quality", which is the claim to be careful about.** The method does
not promise good tasks. It promises tasks whose quality is **decidable**, and
then reports the verdict against itself: by its own acceptance rule
(`cli judge`), **5 of the 6 shipped cells are usable RL data** — `star-docs` 3/3,
`star-names` 2/3 — and at five replicates per cell that is a **measured yield**
rather than an observation. A forge without move 4 cannot tell a task that
teaches coordination from one that is unsolvable, one that is trivial, or one
whose harness is broken; all four print a number, and v1 shipped a dimension at
reward 1.0 on 12 of 12 runs because nothing here was watching. The yield is an
output. Quality is measured, never asserted.

**That number was 1 of 6 until the seeds landed, and the correction is the rule
working rather than a result improving.** Nothing about the tasks changed.
`star-docs` tied the control on two of three tasks at one seed, so the cell rule
called it NO_BITE; at five seeds those same cells spread below the ceiling and
became VALID. `validity.py` sets `SEEDS_FOR_YIELD = 5` and refuses to call one
draw a yield precisely because a single point has no variance to read — so the
repo spent two versions reporting a number its own rule labelled *observed
only*. The failure mode this method exists to avoid is a metric nobody checked;
under-reading your own result is the same error pointed the other way.

**What it is not:** a demonstrated curriculum, and not a method demonstrated on
more than one substrate. Five seeds price the knob; **three tasks from one task
family still cannot price the method**. The next run is task families, not
scale.

## Layout

| | |
|---|---|
| `forge/appworld/` | the pipeline: `select` (roster from the task) · `seams` (cross-app information gate) · `partition` (constraints) · `runtime` (Main + specialists) · `sandbox` (what specialist code may touch) · `reference` (the solutions) · `validity` (which rendered cells are usable RL data) · `harbor` (packaging) · `cli` |
| `forge/maf/` | the earlier from-scratch forge; `parallel-scheduling` ships, two dimensions are quarantined (below) |
| `tasks/` | rendered Harbor tasks |
| `sweep/` | measurement evidence — one file per claim |
| `scripts/` | the probes that produced it |
| `skills/` | **the method** — canonical, substrate-independent, and the failure modes it was built from |

### Porting this to another substrate

`forge/appworld/` is one instantiation, and it is worth knowing which files carry
the method and which are AppWorld glue, because only the second column is thrown
away:

| file | ports? |
|---|---|
| `validity.py` | **the method.** Floor, control, sandwich rule, yield. Needs only a score, a floor and a control — nothing AppWorld |
| `partition.py` | **the method.** The four constraint families, none of which can reach a judge |
| `seams.py` · `select.py` | **the rule ports, the regex does not.** "The roster is what the reference solution touches" is substrate-independent; `apis\.(\w+)\.(\w+)\(` is not. So is the strict filter — every substrate has infrastructure that masquerades as a collaborator |
| `runtime.py` · `sandbox.py` · `container/` | **glue.** Main + specialists, what model-written code may touch, the sidecar boundary. Reimplemented per substrate |
| `reference.py` · `harbor.py` · `cli.py` | **glue.** Solutions, packaging, entry points |

Every number in the write-up names the file that produced it:

| evidence | question |
|---|---|
| `appworld_knobs_v5.json` | does each knob move the score against the control? |
| `appworld_knobs_v3.json` | superseded: same knobs, measured before the `star-docs` arm had docs. Kept because §5 cites the difference |
| `appworld_donothing.json` | where is the floor? |
| `appworld_api_catalog.json` | what did truncating the API catalog destroy? |
| `appworld_injection.json` | can a brief make a specialist leak the reward token? |
| `appworld_oracle.json` | do the shipped solutions actually pass? |
| `appworld_span.json` | which of AppWorld's 147 tasks can carry a partition? |
| `appworld_seams.json` | which multi-app tasks actually move a fact across apps? |
| `tom_degeneracy.json` | v1's `theory-of-mind`: 12 of 12 runs at reward 1.0, zero gradient |
| `appworld_confound.json` | was the drop the partition, or the weaker specialist model? |
| `appworld_rate_limit_cost.json` | what does a rollout cost under a TPM ceiling? |

## Setup

```bash
uv sync --locked                 # runtime + pytest, Ruff, and Pyright
uv run appworld install          # unpacks the app source
uv run appworld download data    # the 183MB dataset -> ./data
cp .env.example .env             # then put your OPENAI_API_KEY in it
uv tool install 'harbor==0.18.0' # runs the tasks; not a project dependency
```

Harbor is a **tool**, not a library dependency: nothing in `forge/` imports it,
and it is deliberately absent from `pyproject.toml`. Every `harbor run` below
needs it, and needs **Docker running** — the sidecar's first build is ~30 min.

`appworld install` is **required again after any reinstall** of the package — it
unpacks source that `uv sync` wipes. If AppWorld starts raising
`No module named 'appworld.apps.admin'`, that is what happened.

The pins are not cosmetic: they are exactly what
`forge/appworld/container/Dockerfile.sidecar` installs, so the sweep measures the
same AppWorld the shipped task runs. `forge/tests/test_environment.py` fails if
they drift.

```bash
uv run pytest
uv run ruff check forge scripts
uv run pyright
```

Building the optional PDFs also requires `latexmk` and XeLaTeX on `PATH`
(MacTeX supplies both on macOS); run `bash scripts/build_report.sh` after those
system tools are installed.

## Quickstart

**Watch one episode happen, message by message** — no Docker, ~2 minutes. The
fastest way to understand what this actually does:

```bash
set -a && . ./.env && set +a                          # OPENAI_API_KEY

uv run python -m scripts.watch_episode --config star-docs    # the partition
uv run python -m scripts.watch_episode --config open         # the control
uv run python -m scripts.watch_episode --config star-names   # the knob that bites
```

It prints the Main's briefs, each specialist's code, the sandbox's verdict on
that code, what AppWorld printed back, and the score against the floor.

**The measurements** (each writes its evidence file):

```bash
uv run python -m scripts.appworld_donothing_probe    # where is the floor?      (no LLM)
uv run python -m scripts.appworld_catalog_probe      # what did truncation kill? (no LLM)
uv run python -m scripts.appworld_injection_probe    # can a brief leak the token? (no LLM)
uv run python -m scripts.appworld_knob_sweep --tasks 3 --out sweep/appworld_knobs_v5.json
```

**The pipeline:**

```bash
# derive task-determined rosters, then require information to cross between them
uv run python -m forge.appworld.cli measure --out sweep/appworld_span.json
uv run python -m forge.appworld.cli seams --out sweep/appworld_seams.json

# render Harbor tasks: 3 AppWorld tasks x 2 shipped configurations
uv run python -m forge.appworld.cli render --n 3 --out tasks
```

**In containers** (the real deliverable — first build is ~30 min, then ~2 min):

```bash
# the reference solution
harbor run --path tasks/appworld-star-docs-binf-2a163ab_1 \
    --agent oracle -n 1 --env-file .env -o jobs/mine     # success=True, reward 1.0

# a real Main
harbor run --path tasks/appworld-star-names-binf-2a163ab_1 \
    --agent terminus-2 --model openai/gpt-5.6-sol -n 1 --env-file .env
```

Read the result — `breakdown.json` is the interesting one, not `reward.txt`:

```bash
uv run python -m json.tool jobs/mine/*/appworld-*/verifier/breakdown.json
```

| field | what it tells you |
|---|---|
| `partial` | the score. **Compare to the 0.333 floor before anything else.** |
| `failed` | *which* requirements failed, by name |
| `ledger[].brief` | what the Main actually said to each specialist |
| `ledger[].report` | what came back — **read this first when a number looks wrong** |
| `ledger[].blocked_reasons` | the sandbox refusing something, and why |

The oracle is **probabilistic**: it replays the decomposition a competent Main
would find, but the specialists are real LLMs doing the real work, so it needs
`OPENAI_API_KEY` at verification time and costs tokens.

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
because the write-up's argument is built on them: they are what a green dashboard
looks like when it is measuring nothing.

## Tests

```bash
uv run pytest
uv run ruff check forge scripts
uv run pyright
```

The two xfails are deliberate: the quarantined dimensions failing their gate — the
gate working, not a defect.
