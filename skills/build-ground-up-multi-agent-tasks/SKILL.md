---
name: build-ground-up-multi-agent-tasks
description: Build complete multi-agent RL or evaluation tasks from first principles, including the task instruction, executable world, role boundaries, generator, reference solution, verifier, audits, debugging surfaces, and one-command delivery package. Use when inventing a new multi-agent task family without deriving it from an existing benchmark, when reviewing a ground-up generator before release, or when converting a task concept into independently validated runnable artifacts. Do not use for partitioning an existing benchmark with an inherited verifier; use constraint-forged-multi-agent-tasks for that path.
---

# Build Ground-Up Multi-Agent Tasks

## Standard

Create evidence that a task is accurate; never describe it as flawless by
construction. Ground-up work designs both the world and its judge, so agreement
between them is not independent evidence. Counter this with separate
implementations, mutation tests, blinded review, adversarial attacks, and
clean-room replay.

Do not deliver a concept, partial scaffold, green unit tests, or an unexecuted
container. Deliver a package that a new operator can run from a clean checkout
with one documented command and whose audit report proves every release gate
passed.

Use `constraint-forged-multi-agent-tasks` instead when the task, world, and
trusted verifier already exist. Never mix evidence from the inherited-verifier
path with claims about a newly designed verifier.

## Required output

Produce one self-contained task family with this minimum structure:

```text
<task-family>/
├── task-spec.json
├── instruction.md
├── environment/
├── generator/
├── protocol/
├── verifier/
├── solution/
├── tests/
├── audit/
│   ├── requirements-trace.json
│   ├── ambiguity-review.json
│   ├── design-provenance.json
│   ├── threat-model.md
│   ├── verifier-validation.json
│   ├── mutation-report.json
│   ├── run-report.json
│   ├── execution-logs/
│   └── known-limitations.md
├── run.sh
└── validate.sh
```

Copy `assets/task-spec.template.json` to `task-spec.json` first. Replace every
placeholder; the validator rejects drafts and missing evidence.

## Objective execution semantics

Put these rules in the task contract and every agent-facing instruction:

1. Ground each external write in one explicit obligation or one observed
   trigger.
2. Do not fire conditional actions until their conditions are observed.
3. Treat creation or first observation as the monitoring baseline. Treat
   “update” or “change” as a later observed transition unless the instruction
   explicitly includes the initial state.
4. Complete each distinct obligation or trigger exactly once successfully.
   Retry only an explicitly failed or rejected operation.
5. Let one action satisfy overlapping requirements when it objectively does so.
   Require separate actions only when the instruction specifies different
   recipients, times, contents, or repetitions.
6. Check the action ledger before every side effect. Do not add actions merely
   to cover an ambiguous interpretation.

Define task-specific terms such as “update,” “done,” “notify,” “cancel,”
“failure,” and “retry” in `task-spec.json`. If two competent reviewers can
derive materially different valid write sets, the instruction is not ready.

## Workflow

Execute these stages in order. Treat every gate as fail-closed: `unknown`,
`untested`, and `not applicable` without a written justification are failures.

### 1. Charter the capability

Write a one-sentence capability claim and a falsifiable counterfactual:

```text
The task measures <decision> because <information/action boundary>.
If that boundary is removed, <control> should improve.
If required collaboration is disabled, <failure mode> should occur.
```

Name non-goals. Keep one primary capability per experimental cell. Reject
dimensions that can be solved by copying a procedure from the instruction,
guessing a planted pattern, or using a decorative extra role.

Start from the capability claim and state machine, not from benchmark examples.
Do not copy or adapt an existing benchmark's instruction, data schema, world,
trajectory, gold actions, generator, or verifier. Record all design inputs and
the results of two independent provenance reviews in
`audit/design-provenance.json`. If any task-defining artifact is inherited,
stop and route the work to `constraint-forged-multi-agent-tasks`.

### 2. Specify the task before implementing it

Assign immutable requirement IDs (`R1`, `R2`, ...). For each requirement, write:

- preconditions and the event that makes it due;
- allowed state changes;
- forbidden side effects;
- terminal postconditions;
- cardinality and exact-once semantics;
- an observable verifier check;
- at least one negative example.

Represent conditional behavior as a state machine or dependency DAG. Define
initial state, trigger, transition, due actions, and terminal state. Never hide
semantics only in a reference trajectory.

Run an ambiguity review before writing code. Give the instruction alone to two
independent reviewers. Ask each for the complete required write set and
conditional branches. Reconcile every disagreement by changing the instruction
or contract, not by silently choosing the oracle’s interpretation.

“Independent” means two distinct reviewer principals in separate executions,
neither of whom authored the task, each starting from a fresh blinded context.
Two passes by one agent, two labels invented by one process, or self-review
disclosed as a limitation do not satisfy this gate. If distinct reviewers are
unavailable, return `QUARANTINED`; never synthesize their attestations.

### 3. Design three independent implementations

Keep these logically separate:

1. **Generator/world:** creates instances and executes actions.
2. **Reference solution:** demonstrates at least one valid policy.
3. **Verifier:** judges outcomes and forbidden side effects.

Do not import generator decision logic into the verifier. Do not let the
reference solution call verifier helpers. Shared code may contain only neutral
types, serialization, and stable identifiers.

Prefer terminal-state verification. If ordering matters, verify only the
minimal causal events required by the instruction. Never require one exact
trajectory when multiple policies reach the same valid state.

If any score depends on an LLM or human rubric, treat it as a measured model:
build a blinded labeled set, report agreement, precision, recall, confidence
intervals, and abstentions, and keep subjective components separate from the
objective reward. Do not market an unvalidated rubric as objective.

### 4. Build the world for replay and diagnosis

Make initial state serializable, seeded, resettable, and hashable. Control time,
randomness, IDs, and external services. Record:

- every user, Main, specialist, tool, wait, environment, and stop event;
- arguments, results, status, simulated time, actor, and causal parent;
- state snapshots or deterministic state diffs around every write;
- generator seed, task version, contract hash, models, and dependency lock;
- infrastructure errors separately from policy failures.

Provide deterministic fault injection for every recovery branch. Never depend
on wall-clock races or live third-party state for the release test.

Trigger later world phases from observable state transitions, never from a
judge's equivalence match on earlier agent output. A world whose reply
arrives only when the verifier decides the agent's email matched gold
couples episode dynamics to judge strictness — measured on the inherited
substrate at corpus scale, that gate froze phase two in 128 of 128
judge-gated cells regardless of agent quality. The verifier may score turn
equivalence; the world must not wait on it.

### 5. Make collaboration necessary

Design the dependency graph before assigning roles. Every specialist must own a
unique necessary action, fact, or permission. The Main must lack direct access
to specialist tools and private state.

Prove role necessity with counterfactual tests:

- the unconstrained control can solve the task;
- the reference team can solve the constrained task;
- removing each required role makes at least one requirement impossible;
- merging all roles removes the intended coordination pressure;
- no role can obtain another role’s private information through undocumented
  tools, files, environment variables, logs, or error messages.

Enforce access, topology, and visibility in code. Prompt-only restrictions are
documentation, not security.

Make the tool interface honest, because models fill every gap with priors
(each rule below traces to a measured failure on the inherited substrate):

- Render complete tool catalogs including every argument description — the
  valid enum values and formats live there, and a specialist shown only
  `service_type: str` guesses, errors, or declines.
- State the simulated clock in every role's prompt; a specialist that is
  not told the date books the model's real-world today.
- Instruct workers to execute the doable parts of a request and name the
  part they cannot do, precisely — never to report tools as unavailable —
  and have the runtime reject a checkably false capability claim (a
  zero-call turn blaming infrastructure) without charging any budget.
- Ground private-reasoning models' execution state explicitly ("no tool
  calls have run yet; the interface is live"): such models sometimes
  imagine calls inside hidden reasoning, observe nothing, and honestly
  report an outage that never happened.
- Keep all temporality with the coordinator: workers act immediately and
  singly; briefs that ask for scheduling or monitoring get refusals.

Run policies outside the trusted world process, using process, container, or VM
isolation. Prove with a boundary test that agent-visible files, environment
variables, process state, logs, errors, and tool outputs contain no other
role’s private state, verifier secrets, or oracle data. An API view that hides a
secret still resident in arbitrary policy code’s process is not isolation.

Expose delegation efficiency as an adjustable configuration value. Derive its
default target from a successful reference policy and the task's causal graph,
then validate the target against alternative valid policies. Going above the
target must continue the episode and reduce only a completion-gated auxiliary
reward. It must never block a delegation, force `DONE`, change primary task
success, or make a valid policy impossible. Hard caps belong only in separately
named robustness experiments and cannot be release gates for the base task.

### 6. Generate instances under explicit invariants

Generate from typed schemas and bounded domains. Validate every candidate
before admitting it:

- exactly one unambiguous instruction maps to the contract;
- at least one reference solution succeeds from a fresh reset;
- all required branches are reachable across the family;
- IDs, names, dates, and quantities are internally consistent;
- no answer, oracle event, seed shortcut, or verifier secret reaches the agent;
- duplicates and near-duplicates are detected;
- difficulty knobs change one variable and preserve solvability.

Record rejection reasons and yield. Never loop until something passes and then
discard the failed population.

### 7. Validate the verifier, not just the solution

Read `references/review-gates.md` before implementing review tests.

At minimum:

- run positive cases, boundary cases, and every conditional branch;
- mutate or omit each required action and confirm the verifier fails;
- add every forbidden side effect and confirm the verifier fails;
- replay, duplicate, reorder, forge, and partially execute actions;
- corrupt logs while preserving state, and state while preserving logs;
- run do-nothing, random-valid, greedy, and exploit policies;
- test stale, malformed, and cross-version artifacts;
- sabotage each security boundary and observe a failing test.

Require all critical mutants killed and report the full mutation matrix. A
green verifier tested only against its own reference solution is unvalidated.

### 8. Measure task usefulness

Keep correctness and coordination efficiency separate. The primary reward must
express task success; budgets and efficiency are auxiliary signals and must
never make a correct task impossible.

Use a transparent auxiliary reward such as:

```text
economy = success * max(0, 1 - max(0, delegations - target) / scale)
```

Version the target, derivation evidence, and scale. Report task success and
economy separately; never collapse them into a pass/fail counter.

Stamp reward-formation annotations beside the primary reward, never instead
of it: a graded, monotone partial credit derived from the contract's
obligations (performing more of them never scores less — the group-mean
floor a group-relative optimizer needs), and a located first-fault pivot so
training can replay the prefix and optimize the suffix. Validate the
annotator like any verifier: it must run blind to the verdict, every
successful episode must show full obligation coverage, and its pivots must
agree with independently hand-audited trajectories — checked against
chronology, not memory. Distinguish structured-argument deviations (a wrong
time, identifier, or enum: a fault) from prose paraphrase (a scoring floor,
never a fault), and exclude legitimate probe errors from fault status.

Measure at least:

- do-nothing floor;
- unconstrained control;
- deterministic reference solution;
- constrained reference team;
- multiple policy/model seeds;
- failure distribution by requirement and mechanism;
- variance and non-degenerate learning signal.

Reject tasks that are unsolvable, trivial, always saturated, always at the
floor, dominated by infrastructure failures, or unable to distinguish the
claimed capability from instruction following.

### 9. Review independently

Use separate passes with fresh context:

1. specification reviewer: reconstruct required writes from the instruction;
2. verifier reviewer: inspect only contract, verifier, and tests;
3. red-team reviewer: attempt leakage, forgery, bypass, and reward hacking;
4. operator reviewer: run the packaged task without author knowledge.

Record the author principal, reviewer principal, execution ID, and blinding
state. A single person or agent may not impersonate multiple independent
reviewers. Automation may check the evidence shape, but it cannot prove the
attestations are truthful; preserve raw review outputs for audit.

Do not give reviewers the intended diagnosis. Give raw artifacts and record
findings, severity, disposition, and regression test. Any critical finding
reopens the relevant earlier gate.

### 10. Package and prove delivery

Pin dependencies and make `run.sh` the supported execution path. Make
`validate.sh` execute, in order:

1. static package validation;
2. unit and integration tests;
3. verifier mutation tests;
4. adversarial tests;
5. deterministic reference solve;
6. do-nothing baseline;
7. clean-room end-to-end run;
8. artifact and hash checks.

Write every command, exit code, version, hash, and result to
`audit/run-report.json`. Run from a clean checkout or fresh container. Then run:

```bash
python skills/build-ground-up-multi-agent-tasks/scripts/validate_task_package.py \
  <task-family>
```

Do not deliver while any placeholder, stale report, skipped critical test,
unreviewed ambiguity, unpinned dependency, undocumented limitation, or failing
gate remains.

Generate run-report rows from captured subprocess results, never by iterating
over the command manifest and stamping success. Store hashed stdout and stderr
for each command under `audit/execution-logs/`, with its execution ID and
timezone-aware start/end timestamps. The clean-room operator principal must
differ from the task author. A report can establish traceability, not truth by
itself; the independent operator must actually reproduce it.

## Release decision

Return exactly one of:

- `READY`: every required gate passed in the packaged path and the evidence is
  current.
- `QUARANTINED`: the package runs, but a named ambiguity, verifier limitation,
  leakage risk, or non-degenerate-signal gate failed.
- `BLOCKED`: the package cannot run or cannot produce independent correctness
  evidence.

Never downgrade `QUARANTINED` or `BLOCKED` to a prose caveat beneath a success
claim.

## Resources

- `assets/task-spec.template.json`: canonical manifest to copy into each task.
- `scripts/validate_task_package.py`: fail-closed structural and evidence
  validator.
- `references/review-gates.md`: detailed verifier, security, reproducibility,
  and delivery review matrices. Read it before stages 7–10.
- `references/audit-schemas.md`: minimum machine-readable evidence shapes
  consumed by the validator.
