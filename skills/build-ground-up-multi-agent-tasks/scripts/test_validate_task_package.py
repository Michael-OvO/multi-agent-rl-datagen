#!/usr/bin/env python3
"""Regression tests for the ground-up task package validator."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from validate_task_package import json_sha256, tree_sha256, validate_package

COMMANDS = {
    "setup": "./setup.sh",
    "validate": "./validate.sh",
    "smoke": "./smoke.sh",
    "test": "./test.sh",
    "oracle": "./oracle.sh",
    "baseline": "./baseline.sh",
    "adversarial": "./adversarial.sh",
    "run": "./run.sh",
}


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def write_json(path: Path, value: object) -> None:
    write_text(path, json.dumps(value, indent=2) + "\n")


def build_ready_fixture(root: Path) -> dict[str, object]:
    instruction_text = (
        "Coordinate alpha and beta. Record one result after both specialists "
        "return their private facts.\n"
    )
    write_text(root / "instruction.md", instruction_text)
    instruction_digest = hashlib.sha256(instruction_text.encode()).hexdigest()

    for component in ("environment", "generator", "verifier", "solution"):
        write_text(root / component / "implementation.txt", f"{component} v1\n")
    for role in ("main", "alpha", "beta"):
        write_text(
            root / "tests" / f"test_role_{role}.py",
            "def test_role():\n    assert True\n",
        )
    write_text(
        root / "tests" / "test_security_boundary.py",
        "def test_security_boundary():\n    assert True\n",
    )
    for command in COMMANDS.values():
        launcher = root / command.removeprefix("./")
        write_text(launcher, "#!/bin/sh\nexit 0\n")
        launcher.chmod(0o755)

    write_json(
        root / "audit" / "ambiguity-review.json",
        {
            "status": "pass",
            "instruction_sha256": instruction_digest,
            "reviewers": [
                {
                    "id": "reviewer-a",
                    "principal_id": "principal-a",
                    "execution_id": "ambiguity-execution-a",
                    "independent": True,
                    "fresh_context": True,
                    "blinded": True,
                    "self_review": False,
                    "required_write_set": ["R1"],
                },
                {
                    "id": "reviewer-b",
                    "principal_id": "principal-b",
                    "execution_id": "ambiguity-execution-b",
                    "independent": True,
                    "fresh_context": True,
                    "blinded": True,
                    "self_review": False,
                    "required_write_set": ["R1"],
                },
            ],
            "unresolved_disagreements": [],
        },
    )
    write_json(
        root / "audit" / "design-provenance.json",
        {
            "status": "pass",
            "origin": "ground-up",
            "benchmark_derivation": False,
            "design_inputs": ["capability charter", "domain documentation"],
            "copied_task_artifacts": [],
            "reviewers": [
                {
                    "id": "provenance-reviewer-a",
                    "principal_id": "principal-a",
                    "execution_id": "provenance-execution-a",
                    "independent": True,
                    "fresh_context": True,
                    "blinded": True,
                    "self_review": False,
                },
                {
                    "id": "provenance-reviewer-b",
                    "principal_id": "principal-b",
                    "execution_id": "provenance-execution-b",
                    "independent": True,
                    "fresh_context": True,
                    "blinded": True,
                    "self_review": False,
                },
            ],
            "unresolved_findings": [],
        },
    )
    write_json(
        root / "audit" / "requirements-trace.json",
        {
            "requirements": [
                {
                    "id": "R1",
                    "positive_tests": ["tests/test_contract.py::test_valid"],
                    "negative_tests": ["tests/test_contract.py::test_missing"],
                }
            ]
        },
    )
    write_json(
        root / "audit" / "verifier-validation.json",
        {
            "status": "pass",
            "cases": {
                "positive": 1,
                "negative": 1,
                "boundary": 1,
                "conditional": 1,
            },
            "false_accepts": 0,
            "false_rejects": 0,
        },
    )
    write_json(
        root / "audit" / "mutation-report.json",
        {
            "status": "pass",
            "critical_kill_rate": 1.0,
            "overall_kill_rate": 0.95,
            "surviving_critical_mutants": [],
        },
    )
    write_text(
        root / "audit" / "threat-model.md", "# Threat model\n\nBoundaries reviewed.\n"
    )
    write_text(
        root / "audit" / "known-limitations.md",
        "# Known limitations\n\nNone critical.\n",
    )

    objective_contract = {
        "success": "R1 passes and no forbidden side effect occurs.",
        "failure": "R1 fails or a forbidden side effect occurs.",
        "conditional_semantics": {
            "baseline": "First observation establishes the baseline.",
            "update": "A later observed transition away from the baseline.",
            "exact_once": "One successful effect per obligation or trigger.",
        },
        "coordination_efficiency": {
            "enabled": True,
            "target_parameter": "delegation_target",
            "delegation_target": 2,
            "target_derivation": "One necessary delegation to each specialist.",
            "adjustable": True,
            "hard_cap": False,
            "completion_gated": True,
            "above_target": "continue-and-penalize",
            "reward_formula": "success * max(0, 1 - overage / 2)",
        },
        "requirements": [
            {
                "id": "R1",
                "statement": "Record one combined result.",
                "preconditions": ["Both private facts are observed."],
                "trigger": "Both specialists return successfully.",
                "allowed_side_effects": ["Create one combined result."],
                "forbidden_side_effects": ["Create a duplicate result."],
                "postconditions": ["Exactly one combined result exists."],
                "cardinality": "exactly-one",
                "verifier_check": "Count the terminal combined results.",
                "negative_case": "A duplicate combined result fails.",
            }
        ],
    }
    spec: dict[str, object] = {
        "schema_version": "1.0",
        "task_id": "synthetic-ground-up-task",
        "task_version": "0.1.0",
        "status": "ready",
        "purpose": {
            "origin": "ground-up",
            "benchmark_derivation": False,
            "author_principal": "author-principal",
            "capability_claim": "Transfer two private facts through a coordinator.",
            "counterfactual": "Removing either role makes R1 impossible.",
            "non_goals": ["Natural-language style"],
        },
        "instruction": {
            "path": "instruction.md",
            "sha256": instruction_digest,
            "defined_terms": {
                "update": "A post-baseline transition.",
                "done": "All postconditions hold.",
                "retry": "Repeat only an explicitly failed operation.",
            },
            "ambiguity_review": {
                "status": "pass",
                "reviewers": ["reviewer-a", "reviewer-b"],
                "agreement": "unanimous",
                "evidence": "audit/ambiguity-review.json",
            },
        },
        "objective_contract": objective_contract,
        "roles": [
            {
                "name": "main",
                "kind": "coordinator",
                "permissions": [],
                "private_information": [],
                "necessity_test": "tests/test_role_main.py",
            },
            {
                "name": "alpha",
                "kind": "specialist",
                "permissions": ["read alpha fact"],
                "private_information": ["alpha fact"],
                "necessity_test": "tests/test_role_alpha.py",
            },
            {
                "name": "beta",
                "kind": "specialist",
                "permissions": ["read beta fact"],
                "private_information": ["beta fact"],
                "necessity_test": "tests/test_role_beta.py",
            },
        ],
        "world": {
            "implementation": "environment/",
            "deterministic_replay": True,
            "seed": "fixed-seed",
            "clock": "simulated",
            "reset_command": "./reset.sh",
            "state_export_command": "./state.sh",
            "fault_injection": "seeded",
            "agent_isolation": "process",
            "secret_absent_from_agent_namespace": True,
            "security_boundary_test": "tests/test_security_boundary.py",
        },
        "generator": {
            "implementation": "generator/",
            "command": "./generate.sh",
            "schema": "schema.json",
            "records_rejections": True,
        },
        "verifier": {
            "implementation": "verifier/",
            "command": "./verify.sh",
            "independent_from_generator": True,
            "terminal_state_primary": True,
            "checks_forbidden_side_effects": True,
            "critical_mutation_kill_rate": 1.0,
            "overall_mutation_kill_rate": 0.95,
            "subjective_component": False,
            "human_validation": None,
        },
        "reference_solution": {
            "implementation": "solution/",
            "command": "./solve.sh",
            "independent_from_verifier": True,
        },
        "commands": COMMANDS,
        "artifacts": {
            "requirements_trace": "audit/requirements-trace.json",
            "design_provenance": "audit/design-provenance.json",
            "threat_model": "audit/threat-model.md",
            "verifier_validation": "audit/verifier-validation.json",
            "mutation_report": "audit/mutation-report.json",
            "run_report": "audit/run-report.json",
            "known_limitations": "audit/known-limitations.md",
        },
        "acceptance": {
            "positive_cases_pass": True,
            "negative_cases_fail": True,
            "do_nothing_measured": True,
            "reference_passes": True,
            "role_necessity_passes": True,
            "clean_room_replay_passes": True,
            "no_placeholders": True,
        },
    }
    write_json(root / "task-spec.json", spec)
    command_rows = []
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for index, (name, command) in enumerate(COMMANDS.items()):
        stdout_path = root / "audit" / "execution-logs" / f"{name}.stdout"
        stderr_path = root / "audit" / "execution-logs" / f"{name}.stderr"
        write_text(stdout_path, f"{name} passed\n")
        write_text(stderr_path, "")
        started = start + timedelta(seconds=index * 2)
        finished = started + timedelta(seconds=1)
        command_rows.append(
            {
                "name": name,
                "command": command,
                "exit_code": 0,
                "execution_id": f"{name}-execution",
                "started_at": started.isoformat(),
                "finished_at": finished.isoformat(),
                "stdout_path": stdout_path.relative_to(root).as_posix(),
                "stdout_sha256": hashlib.sha256(stdout_path.read_bytes()).hexdigest(),
                "stderr_path": stderr_path.relative_to(root).as_posix(),
                "stderr_sha256": hashlib.sha256(stderr_path.read_bytes()).hexdigest(),
            }
        )
    write_json(
        root / "audit" / "run-report.json",
        {
            "status": "pass",
            "task_version": "0.1.0",
            "clean_room": True,
            "runner": {
                "principal_id": "operator-principal",
                "execution_id": "operator-execution",
                "clean_environment": True,
            },
            "hashes": {
                "objective_contract": json_sha256(objective_contract),
                "instruction": instruction_digest,
                "environment": tree_sha256(root / "environment"),
                "generator": tree_sha256(root / "generator"),
                "verifier": tree_sha256(root / "verifier"),
                "reference_solution": tree_sha256(root / "solution"),
            },
            "commands": command_rows,
        },
    )
    return spec


class ValidatorTests(unittest.TestCase):
    def test_ready_package_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_ready_fixture(root)
            self.assertEqual(validate_package(root), [])

    def test_hard_delegation_cap_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = build_ready_fixture(root)
            contract = spec["objective_contract"]
            assert isinstance(contract, dict)
            efficiency = contract["coordination_efficiency"]
            assert isinstance(efficiency, dict)
            efficiency["hard_cap"] = True
            write_json(root / "task-spec.json", spec)
            errors = validate_package(root)
            self.assertTrue(any("hard_cap must be false" in error for error in errors))

    def test_stale_component_hash_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_ready_fixture(root)
            write_text(
                root / "verifier" / "implementation.txt", "changed after audit\n"
            )
            errors = validate_package(root)
            self.assertTrue(any("run report hashes" in error for error in errors))

    def test_synthesized_command_success_without_logs_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_ready_fixture(root)
            report_path = root / "audit" / "run-report.json"
            report = json.loads(report_path.read_text())
            report["commands"] = [
                {"name": name, "command": command, "exit_code": 0}
                for name, command in COMMANDS.items()
            ]
            write_json(report_path, report)
            errors = validate_package(root)
            self.assertTrue(
                any("valid execution evidence" in error for error in errors)
            )

    def test_two_self_reviews_are_not_independent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_ready_fixture(root)
            provenance_path = root / "audit" / "design-provenance.json"
            provenance = json.loads(provenance_path.read_text())
            provenance["reviewers"][0]["principal_id"] = "author-principal"
            provenance["reviewers"][1]["principal_id"] = "author-principal"
            provenance["reviewers"][0]["self_review"] = True
            provenance["reviewers"][1]["self_review"] = True
            write_json(provenance_path, provenance)
            errors = validate_package(root)
            self.assertTrue(
                any("principal IDs must be distinct" in error for error in errors)
            )
            self.assertTrue(
                any(
                    "must differ from the author principal" in error for error in errors
                )
            )
            self.assertTrue(any("not self-review" in error for error in errors))

    def test_malformed_reviewer_and_role_are_reported_without_crash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = build_ready_fixture(root)
            roles = spec["roles"]
            assert isinstance(roles, list) and isinstance(roles[0], dict)
            roles[0]["name"] = ["not", "a", "string"]
            write_json(root / "task-spec.json", spec)
            review_path = root / "audit" / "ambiguity-review.json"
            review = json.loads(review_path.read_text())
            review["reviewers"][0]["id"] = ["not", "hashable"]
            write_json(review_path, review)
            errors = validate_package(root)
            self.assertTrue(any("role name" in error for error in errors))
            self.assertTrue(
                any("ambiguity review evidence" in error for error in errors)
            )


if __name__ == "__main__":
    unittest.main()
