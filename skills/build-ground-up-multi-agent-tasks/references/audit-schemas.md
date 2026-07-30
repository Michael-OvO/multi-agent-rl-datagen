# Audit Schemas

Use these minimum JSON shapes. Additional versioned fields are allowed. The
package validator rejects missing or stale evidence.

## `audit/ambiguity-review.json`

```json
{
  "status": "pass",
  "instruction_sha256": "64-lowercase-hex-characters",
  "reviewers": [
    {
      "id": "reviewer-a",
      "principal_id": "principal-a",
      "execution_id": "execution-a",
      "independent": true,
      "fresh_context": true,
      "blinded": true,
      "self_review": false,
      "required_write_set": ["R1"]
    },
    {
      "id": "reviewer-b",
      "principal_id": "principal-b",
      "execution_id": "execution-b",
      "independent": true,
      "fresh_context": true,
      "blinded": true,
      "self_review": false,
      "required_write_set": ["R1"]
    }
  ],
  "unresolved_disagreements": []
}
```

Reviewers must receive the instruction without the reference trajectory or
verifier. Their principal and execution IDs must be distinct and neither
principal may equal `purpose.author_principal`. A pass requires agreement on the
complete required write set and all conditional branches.

## `audit/design-provenance.json`

```json
{
  "status": "pass",
  "origin": "ground-up",
  "benchmark_derivation": false,
  "design_inputs": ["capability charter", "domain documentation"],
  "copied_task_artifacts": [],
  "reviewers": [
    {
      "id": "provenance-reviewer-a",
      "principal_id": "principal-a",
      "execution_id": "provenance-execution-a",
      "independent": true,
      "fresh_context": true,
      "blinded": true,
      "self_review": false
    },
    {
      "id": "provenance-reviewer-b",
      "principal_id": "principal-b",
      "execution_id": "provenance-execution-b",
      "independent": true,
      "fresh_context": true,
      "blinded": true,
      "self_review": false
    }
  ],
  "unresolved_findings": []
}
```

List every design input precisely in a real package. If any instruction, data
schema, world, trajectory, gold action, generator, or verifier came from a
benchmark, this schema cannot pass. Two passes by the author or the same
reviewer principal cannot pass.

## `audit/requirements-trace.json`

```json
{
  "requirements": [
    {
      "id": "R1",
      "positive_tests": ["tests/test_r1.py::test_valid"],
      "negative_tests": ["tests/test_r1.py::test_missing"]
    }
  ]
}
```

Every contract requirement ID must occur exactly once and have at least one
positive and one negative test ID.

## `audit/verifier-validation.json`

```json
{
  "status": "pass",
  "cases": {
    "positive": 1,
    "negative": 1,
    "boundary": 1,
    "conditional": 1
  },
  "false_accepts": 0,
  "false_rejects": 0
}
```

Counts must come from executed labeled cases, including every conditional
branch. Add the case matrix and command output as versioned fields.

## `audit/mutation-report.json`

```json
{
  "status": "pass",
  "critical_kill_rate": 1.0,
  "overall_kill_rate": 0.95,
  "surviving_critical_mutants": []
}
```

Include the full mutation matrix in a real report. Critical means a mutation
that can alter task success, required cardinality, role security, or a forbidden
side-effect decision.

## `audit/run-report.json`

```json
{
  "status": "pass",
  "task_version": "0.1.0",
  "clean_room": true,
  "runner": {
    "principal_id": "operator-principal",
    "execution_id": "operator-execution",
    "clean_environment": true
  },
  "hashes": {
    "instruction": "sha256",
    "objective_contract": "canonical-json-sha256",
    "environment": "tree-sha256",
    "generator": "tree-sha256",
    "verifier": "tree-sha256",
    "reference_solution": "tree-sha256"
  },
  "commands": [
    {
      "name": "setup",
      "command": "the exact command from task-spec.json",
      "exit_code": 0,
      "execution_id": "setup-execution",
      "started_at": "2026-01-01T00:00:00+00:00",
      "finished_at": "2026-01-01T00:00:01+00:00",
      "stdout_path": "audit/execution-logs/setup.stdout",
      "stdout_sha256": "sha256",
      "stderr_path": "audit/execution-logs/setup.stderr",
      "stderr_sha256": "sha256"
    }
  ]
}
```

Record one successful row for every declared command: `setup`, `validate`,
`smoke`, `test`, `oracle`, `baseline`, `adversarial`, and `run`. Hash a directory
by sorting relative file names and hashing length-prefixed names and contents,
as implemented by `validate_task_package.py`. The runner must differ from
`purpose.author_principal`; command rows must come from real captured subprocess
results, not synthesized success records.
