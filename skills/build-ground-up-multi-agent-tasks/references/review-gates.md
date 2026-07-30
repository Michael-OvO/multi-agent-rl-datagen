# Review Gates

Use this reference during verifier construction, adversarial review, and
delivery. Record every result in `audit/`; do not replace evidence with a
checkmark in prose.

## Contents

1. Requirements trace
2. Ground-up provenance
3. Verifier validation
4. Multi-agent necessity
5. Security and leakage
6. Runtime and observability
7. Reproducibility
8. Statistical usefulness
9. Delivery audit

## 1. Requirements trace

For every immutable requirement ID, record:

| field | required evidence |
|---|---|
| instruction span | exact text that creates the obligation |
| defined terms | meanings needed to derive one write set |
| trigger | observable event that makes the action due |
| allowed effects | complete permitted state-change set |
| forbidden effects | state changes that must fail |
| positive test | minimal valid case |
| negative tests | missing, wrong, duplicate, premature, stale, extra |
| verifier location | independent check implementing the contract |
| mutation | deliberate defect that the test kills |

Reject requirements that can only be checked by comparing against the reference
trajectory. Verify outcomes and minimal causal ordering.

## 2. Ground-up provenance

Freeze the capability charter and state machine before reviewing prior work.
Record every human brief, model prompt, paper, library, dataset, and code asset
that influenced task-defining decisions. Two independent reviewers must confirm
that no benchmark instruction, data schema, world, trajectory, gold action,
generator, or verifier was copied or adapted.

Both reviewers must be distinct principals, run in distinct executions, receive
fresh blinded context, and differ from the recorded author principal. Repeating
the review twice in one agent context is self-review, not independent evidence.
Do not mark it `READY` merely because the limitation is disclosed.

General-purpose libraries and domain facts are allowed when recorded. An
inherited task-defining artifact is not: route that work to the inherited-task
skill and preserve its trusted verifier. A declaration alone is evidence of
process, not proof of novelty, so retain reviewer identities, findings, and
dispositions.

## 3. Verifier validation

Build a labeled matrix before trusting a score:

- canonical success;
- alternative valid order and decomposition;
- boundary values;
- one missing action per requirement;
- wrong argument per field;
- duplicate successful write;
- action before trigger;
- action after stale trigger;
- forbidden extra write;
- partial completion followed by claimed success;
- correct final state with forged trajectory;
- plausible trajectory with wrong final state;
- cross-instance replay;
- cross-version replay;
- malformed and truncated artifacts.

For every verifier branch, make at least one test take the pass edge and one take
the fail edge. Use coverage only as evidence of execution, never correctness.

### Mutation standard

Mutate the verifier and world independently:

- delete each required check;
- invert each comparison;
- relax each cardinality;
- remove each forbidden-side-effect check;
- ignore each dependency edge;
- accept stale IDs or versions;
- expose each secret;
- bypass each role boundary.

Require a 100% kill rate for critical mutants and at least 95% overall. List
survivors individually with disposition. Never average away a surviving
security or reward-integrity mutant.

### Subjective components

If a rubric or model judge remains:

1. Freeze a balanced, blinded human-labeled set.
2. Use at least two independent annotators and adjudicate disagreements.
3. Report class balance, agreement, precision, recall, confidence intervals,
   abstentions, and versioned prompts/models.
4. Keep its score separate from deterministic task success.
5. Quarantine if validation falls below the task family’s declared thresholds.

Apply the same reviewer-independence definition: distinct principals, distinct
executions, fresh blinded contexts, and no task author serving as reviewer.

## 4. Multi-agent necessity

Run these counterfactuals from identical initial state:

| intervention | expected result |
|---|---|
| unconstrained single agent | succeeds; proves world solvability |
| reference team | succeeds; proves constrained solvability |
| do nothing | establishes the actual floor |
| remove role A, B, ... | a named requirement becomes impossible |
| give Main all tools | coordination pressure disappears |
| hide capability docs | only discovery changes |
| remove one information edge | downstream action cannot be completed correctly |
| replace specialist with scripted API proxy | task classification changes; do not call it communication training |

Reject decorative roles and independent fan-out mislabeled as information
transfer. Draw the dependency DAG and identify the exact fact or permission
crossing each role boundary.

Treat a delegation target as an adjustable efficiency heuristic. Exceeding it
must leave the task runnable and primary correctness unchanged. Test the exact
target, target plus one, large overages, and a runtime override. Reject any base
task that refuses a delegation, forces termination, or rewrites failure merely
because the target was exceeded.

## 5. Security and leakage

Threat-model the Main, every specialist, tool outputs, logs, package files,
environment variables, network, process namespace, and verifier phase.

Attempt:

- reading task seeds, generator code, answers, oracle events, tests, or tokens;
- importing verifier/reference modules;
- inspecting process environment and filesystem mounts;
- indirect code execution through strings, templates, notebooks, shells, or
  secondary clients;
- off-roster tool calls and specialist impersonation;
- forged reports, tool results, notifications, and completion messages;
- replaying valid artifacts from another task/version;
- purchasing reward without satisfying terminal state.

Enforce default-deny capabilities at the world boundary. Parse container copy
and mount rules. Verify secrets do not exist during the agent phase; do not rely
only on access-control code around an exposed secret.

The policy must execute outside the trusted world process. Inspect the actual
process/container/VM boundary and fail a sabotage test that exposes private
world memory. A role-scoped API alone does not protect secrets from arbitrary
policy code sharing the same process.

For every fixed exploit, retain the exploit as a regression test and sabotage
the defense to prove that test goes red.

## 6. Runtime and observability

The trajectory must distinguish:

- never ran;
- attempted and failed;
- tool rejected;
- malformed protocol;
- infrastructure error;
- timeout;
- environment stop;
- policy surrender;
- successful completion.

Log actor, action, arguments, result, status, simulated time, causal parent,
state diff, and artifact version. Never reduce named failures to counts only.

Pin tests for:

- complete, untruncated capability catalogs;
- tool output visible to the caller;
- Main and specialist model parity or explicit experiment labels;
- wait semantics and conditional event delivery;
- retries after failure versus duplicate successful writes;
- run and verifier paths using the same packaged code.

## 7. Reproducibility

Require:

- pinned dependencies and base images;
- versioned schemas, contracts, prompts, models, and data;
- deterministic seed capture;
- serializable initial and terminal state;
- no hidden network dependency in release tests;
- clean-checkout and fresh-container execution;
- byte or semantic hashes for instruction, contract, verifier, and environment;
- migration or hard refusal for cross-version artifacts.

Re-run the same instance twice and diff normalized trajectories and terminal
state. Explain every permitted nondeterministic field.

## 8. Statistical usefulness

Separate task correctness from training usefulness.

Measure:

- do-nothing floor and unconstrained ceiling;
- reference success rate;
- constrained success distribution over multiple seeds;
- per-requirement failure mass;
- infrastructure-failure rate;
- score variance and advantage variance;
- task-family generation and rejection yield;
- duplicates and effective diversity;
- knob isolation through one-variable ablations.

Reject zero-variance all-pass and all-fail families, score changes caused by
model confounds, and tasks whose dominant failures are protocol or harness
errors rather than the claimed multi-agent decision.

## 9. Delivery audit

A fresh operator must be able to:

1. clone or unpack the package;
2. run `./validate.sh`;
3. run `./run.sh`;
4. inspect the resulting trajectory and named verifier breakdown;
5. reproduce the recorded reference and baseline results.

Before `READY`, confirm:

- no TODO/TBD/CHANGEME placeholders;
- no skipped critical tests;
- all audit paths in `task-spec.json` exist;
- `audit/run-report.json` matches the current task version and contract hash;
- every required command is recorded with exit code 0;
- every command row has a unique execution ID, timezone-aware start/end times,
  and hashed stdout/stderr files produced by the actual subprocess;
- the clean-room runner principal differs from the author principal;
- known limitations are explicit and non-critical;
- the packaged path, not a developer shortcut, produced the evidence;
- old outputs cannot be mistaken for the current release.

If any item is unknown, return `QUARANTINED` or `BLOCKED`, never `READY`.

Reject reports created by copying declared commands and assigning exit code 0.
Re-run the commands independently and compare the captured logs and hashes.

The machine-readable minimums for these artifacts are defined in
`audit-schemas.md`.
