#!/usr/bin/env python3
"""Fail-closed structural and evidence validation for a ground-up task package."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PLACEHOLDER = re.compile(
    r"(?:\bTODO\b|\bTBD\b|\bCHANGEME\b|<[^>\n]+>)",
    re.IGNORECASE,
)
ID = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")

TOP_LEVEL = {
    "schema_version",
    "task_id",
    "task_version",
    "status",
    "purpose",
    "instruction",
    "objective_contract",
    "roles",
    "world",
    "generator",
    "verifier",
    "reference_solution",
    "commands",
    "artifacts",
    "acceptance",
}
COMMANDS = {
    "setup",
    "validate",
    "smoke",
    "test",
    "oracle",
    "baseline",
    "adversarial",
    "run",
}
ARTIFACTS = {
    "requirements_trace",
    "design_provenance",
    "threat_model",
    "verifier_validation",
    "mutation_report",
    "run_report",
    "known_limitations",
}
ACCEPTANCE = {
    "positive_cases_pass",
    "negative_cases_fail",
    "do_nothing_measured",
    "reference_passes",
    "role_necessity_passes",
    "clean_room_replay_passes",
    "no_placeholders",
}


class Findings:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def require(self, condition: bool, message: str) -> None:
        if not condition:
            self.errors.append(message)


def load_json(path: Path, findings: Findings) -> Any:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        findings.errors.append(f"missing file: {path}")
    except (OSError, json.JSONDecodeError) as exc:
        findings.errors.append(f"cannot read JSON {path}: {exc}")
    return None


def placeholders(value: Any, at: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, str) and PLACEHOLDER.search(value):
        found.append(at)
    elif isinstance(value, dict):
        for key, child in value.items():
            found.extend(placeholders(child, f"{at}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(placeholders(child, f"{at}[{index}]"))
    return found


def safe_path(root: Path, raw: Any, findings: Findings, label: str) -> Path | None:
    if not isinstance(raw, str) or not raw.strip():
        findings.errors.append(f"{label} must be a non-empty relative path")
        return None
    path = (root / raw).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        findings.errors.append(f"{label} escapes the package root: {raw}")
        return None
    findings.require(path.exists(), f"{label} does not exist: {raw}")
    return path


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_sha256(path: Path) -> str:
    """Hash one file or a directory tree, including normalized relative names."""
    if path.is_file():
        return file_sha256(path)
    digest = hashlib.sha256()
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        relative = child.relative_to(path).as_posix().encode()
        payload = child.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def json_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def non_empty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def validate_independent_reviewers(
    rows: Any,
    author_principal: Any,
    findings: Findings,
    label: str,
) -> set[str]:
    findings.require(isinstance(rows, list), f"{label} must be a list")
    if not isinstance(rows, list):
        return set()
    valid_rows = [
        row
        for row in rows
        if isinstance(row, dict)
        and non_empty_text(row.get("id"))
        and non_empty_text(row.get("principal_id"))
        and non_empty_text(row.get("execution_id"))
    ]
    findings.require(
        len(valid_rows) == len(rows) and len(valid_rows) >= 2,
        f"{label} needs at least two fully identified reviewers",
    )
    reviewer_ids = [row["id"] for row in valid_rows]
    principals = [row["principal_id"] for row in valid_rows]
    executions = [row["execution_id"] for row in valid_rows]
    findings.require(
        len(set(reviewer_ids)) == len(reviewer_ids),
        f"{label} IDs must be distinct",
    )
    findings.require(
        len(set(principals)) == len(principals),
        f"{label} principal IDs must be distinct",
    )
    findings.require(
        len(set(executions)) == len(executions),
        f"{label} execution IDs must be distinct",
    )
    findings.require(
        non_empty_text(author_principal)
        and all(principal != author_principal for principal in principals),
        f"{label} principals must differ from the author principal",
    )
    findings.require(
        all(
            row.get("independent") is True
            and row.get("fresh_context") is True
            and row.get("blinded") is True
            and row.get("self_review") is False
            for row in valid_rows
        ),
        f"{label} entries must be independent, fresh-context, blinded, and not self-review",
    )
    return set(reviewer_ids)


def validate_requirements(spec: dict[str, Any], findings: Findings) -> set[str]:
    contract = spec.get("objective_contract")
    findings.require(isinstance(contract, dict), "objective_contract must be an object")
    if not isinstance(contract, dict):
        return set()
    semantics = contract.get("conditional_semantics")
    findings.require(
        isinstance(semantics, dict)
        and all(semantics.get(k) for k in ("baseline", "update", "exact_once")),
        "objective_contract.conditional_semantics must define baseline, update, and exact_once",
    )
    efficiency = contract.get("coordination_efficiency")
    findings.require(
        isinstance(efficiency, dict),
        "objective_contract.coordination_efficiency must be an object",
    )
    if isinstance(efficiency, dict):
        findings.require(
            efficiency.get("enabled") is True,
            "coordination efficiency must be enabled as an auxiliary signal",
        )
        findings.require(
            efficiency.get("target_parameter") == "delegation_target",
            "coordination efficiency target_parameter must be delegation_target",
        )
        target = efficiency.get("delegation_target")
        findings.require(
            isinstance(target, int) and not isinstance(target, bool) and target > 0,
            "coordination efficiency delegation_target must be a positive integer",
        )
        findings.require(
            non_empty_text(efficiency.get("target_derivation")),
            "coordination efficiency target_derivation must be non-empty",
        )
        findings.require(
            efficiency.get("adjustable") is True,
            "coordination efficiency target must be adjustable",
        )
        findings.require(
            efficiency.get("hard_cap") is False,
            "coordination efficiency hard_cap must be false",
        )
        findings.require(
            efficiency.get("completion_gated") is True,
            "coordination efficiency reward must be completion-gated",
        )
        findings.require(
            efficiency.get("above_target") == "continue-and-penalize",
            "above-target behavior must be continue-and-penalize",
        )
        findings.require(
            non_empty_text(efficiency.get("reward_formula")),
            "coordination efficiency reward_formula must be non-empty",
        )
    requirements = contract.get("requirements")
    findings.require(
        isinstance(requirements, list) and bool(requirements),
        "objective_contract.requirements must be a non-empty list",
    )
    ids: list[str] = []
    for index, requirement in enumerate(requirements or []):
        label = f"objective_contract.requirements[{index}]"
        findings.require(isinstance(requirement, dict), f"{label} must be an object")
        if not isinstance(requirement, dict):
            continue
        rid = requirement.get("id")
        findings.require(
            isinstance(rid, str) and re.fullmatch(r"R[1-9][0-9]*", rid) is not None,
            f"{label}.id must match R1, R2, ...",
        )
        if isinstance(rid, str):
            ids.append(rid)
        for field in (
            "statement",
            "trigger",
            "cardinality",
            "verifier_check",
            "negative_case",
        ):
            findings.require(
                isinstance(requirement.get(field), str)
                and bool(requirement[field].strip()),
                f"{label}.{field} must be non-empty",
            )
        for field in (
            "preconditions",
            "allowed_side_effects",
            "forbidden_side_effects",
            "postconditions",
        ):
            findings.require(
                isinstance(requirement.get(field), list),
                f"{label}.{field} must be a list",
            )
    findings.require(len(ids) == len(set(ids)), "requirement IDs must be unique")
    return set(ids)


def validate_roles(root: Path, spec: dict[str, Any], findings: Findings) -> None:
    roles = spec.get("roles")
    findings.require(isinstance(roles, list), "roles must be a list")
    if not isinstance(roles, list):
        return
    coordinators = [
        r for r in roles if isinstance(r, dict) and r.get("kind") == "coordinator"
    ]
    specialists = [
        r for r in roles if isinstance(r, dict) and r.get("kind") == "specialist"
    ]
    findings.require(
        len(coordinators) == 1, "roles must contain exactly one coordinator"
    )
    findings.require(
        len(specialists) >= 2, "roles must contain at least two specialists"
    )
    names = [r.get("name") for r in roles if isinstance(r, dict)]
    valid_names = [name for name in names if isinstance(name, str)]
    findings.require(
        len(valid_names) == len(names)
        and all(ID.fullmatch(name) for name in valid_names),
        "every role name must be a stable lowercase identifier",
    )
    findings.require(
        len(valid_names) == len(set(valid_names)),
        "role names must be unique",
    )
    for role in roles:
        if not isinstance(role, dict):
            findings.errors.append("every role must be an object")
            continue
        name = role.get("name", "?")
        findings.require(
            role.get("kind") in {"coordinator", "specialist"},
            f"role {name} kind must be coordinator or specialist",
        )
        safe_path(
            root, role.get("necessity_test"), findings, f"role {name} necessity_test"
        )
    for role in specialists:
        name = role.get("name", "?")
        findings.require(
            isinstance(role.get("permissions"), list) and bool(role["permissions"]),
            f"specialist {name} must have non-empty permissions",
        )


def validate_evidence(
    root: Path,
    spec: dict[str, Any],
    requirement_ids: set[str],
    findings: Findings,
) -> None:
    artifacts = spec.get("artifacts")
    findings.require(isinstance(artifacts, dict), "artifacts must be an object")
    if not isinstance(artifacts, dict):
        return
    findings.require(
        set(artifacts) == ARTIFACTS,
        f"artifacts keys must be exactly: {', '.join(sorted(ARTIFACTS))}",
    )
    paths = {
        name: safe_path(root, raw, findings, f"artifacts.{name}")
        for name, raw in artifacts.items()
    }

    provenance_path = paths.get("design_provenance")
    provenance = (
        load_json(provenance_path, findings)
        if provenance_path and provenance_path.exists()
        else None
    )
    if isinstance(provenance, dict):
        findings.require(
            provenance.get("status") == "pass",
            "design provenance status must be pass",
        )
        findings.require(
            provenance.get("origin") == "ground-up",
            "design provenance origin must be ground-up",
        )
        findings.require(
            provenance.get("benchmark_derivation") is False,
            "design provenance benchmark_derivation must be false",
        )
        findings.require(
            provenance.get("copied_task_artifacts") == [],
            "design provenance copied_task_artifacts must be empty",
        )
        purpose = spec.get("purpose")
        author_principal = (
            purpose.get("author_principal") if isinstance(purpose, dict) else None
        )
        validate_independent_reviewers(
            provenance.get("reviewers"),
            author_principal,
            findings,
            "design provenance review",
        )
        findings.require(
            isinstance(provenance.get("design_inputs"), list),
            "design provenance design_inputs must be a list",
        )
        findings.require(
            provenance.get("unresolved_findings") == [],
            "design provenance must have no unresolved findings",
        )

    trace_path = paths.get("requirements_trace")
    trace = (
        load_json(trace_path, findings) if trace_path and trace_path.exists() else None
    )
    if isinstance(trace, dict):
        traced = trace.get("requirements")
        findings.require(
            isinstance(traced, list),
            "requirements trace must contain a requirements list",
        )
        trace_ids = {
            row.get("id")
            for row in traced or []
            if isinstance(row, dict) and isinstance(row.get("id"), str)
        }
        findings.require(
            trace_ids == requirement_ids,
            "requirements trace IDs must exactly match the objective contract",
        )
        for row in traced or []:
            if not isinstance(row, dict):
                continue
            rid = row.get("id", "?")
            findings.require(
                isinstance(row.get("positive_tests"), list)
                and bool(row["positive_tests"]),
                f"requirements trace {rid} needs positive_tests",
            )
            findings.require(
                isinstance(row.get("negative_tests"), list)
                and bool(row["negative_tests"]),
                f"requirements trace {rid} needs negative_tests",
            )
            for kind in ("positive_tests", "negative_tests"):
                tests = row.get(kind)
                findings.require(
                    isinstance(tests, list)
                    and all(non_empty_text(test) for test in tests),
                    f"requirements trace {rid} {kind} must contain non-empty test IDs",
                )

    mutation_path = paths.get("mutation_report")
    mutation = (
        load_json(mutation_path, findings)
        if mutation_path and mutation_path.exists()
        else None
    )
    if isinstance(mutation, dict):
        findings.require(
            mutation.get("status") == "pass", "mutation report status must be pass"
        )
        findings.require(
            mutation.get("critical_kill_rate") == 1.0,
            "critical mutation kill rate must be 1.0",
        )
        overall = mutation.get("overall_kill_rate")
        findings.require(
            isinstance(overall, (int, float)) and overall >= 0.95,
            "overall mutation kill rate must be at least 0.95",
        )
        findings.require(
            not mutation.get("surviving_critical_mutants"),
            "no critical mutant may survive",
        )
        verifier = spec.get("verifier")
        if isinstance(verifier, dict):
            findings.require(
                mutation.get("critical_kill_rate")
                == verifier.get("critical_mutation_kill_rate")
                and mutation.get("overall_kill_rate")
                == verifier.get("overall_mutation_kill_rate"),
                "mutation report rates must match the verifier declaration",
            )

    validation_path = paths.get("verifier_validation")
    validation = (
        load_json(validation_path, findings)
        if validation_path and validation_path.exists()
        else None
    )
    if isinstance(validation, dict):
        findings.require(
            validation.get("status") == "pass",
            "verifier validation status must be pass",
        )
        cases = validation.get("cases")
        findings.require(
            isinstance(cases, dict)
            and all(
                isinstance(cases.get(kind), int)
                and not isinstance(cases.get(kind), bool)
                and cases[kind] > 0
                for kind in ("positive", "negative", "boundary", "conditional")
            ),
            "verifier validation cases must contain positive counts for "
            "positive, negative, boundary, and conditional",
        )
        findings.require(
            validation.get("false_accepts") == 0,
            "verifier validation false_accepts must be 0",
        )
        findings.require(
            validation.get("false_rejects") == 0,
            "verifier validation false_rejects must be 0",
        )

    run_path = paths.get("run_report")
    run = load_json(run_path, findings) if run_path and run_path.exists() else None
    if isinstance(run, dict):
        findings.require(run.get("status") == "pass", "run report status must be pass")
        findings.require(
            run.get("task_version") == spec.get("task_version"),
            "run report task_version must match task-spec.json",
        )
        findings.require(
            run.get("clean_room") is True,
            "run report clean_room must be true",
        )
        runner = run.get("runner")
        purpose = spec.get("purpose")
        author_principal = (
            purpose.get("author_principal") if isinstance(purpose, dict) else None
        )
        findings.require(
            isinstance(runner, dict), "run report runner must be an object"
        )
        if isinstance(runner, dict):
            findings.require(
                non_empty_text(runner.get("principal_id"))
                and runner.get("principal_id") != author_principal,
                "run report runner principal must differ from the author principal",
            )
            findings.require(
                non_empty_text(runner.get("execution_id")),
                "run report runner execution_id must be non-empty",
            )
            findings.require(
                runner.get("clean_environment") is True,
                "run report runner clean_environment must be true",
            )
        expected_hashes: dict[str, str] = {
            "objective_contract": json_sha256(spec.get("objective_contract")),
        }
        instruction = spec.get("instruction")
        if isinstance(instruction, dict):
            instruction_path = safe_path(
                root,
                instruction.get("path"),
                findings,
                "run report instruction hash source",
            )
            if instruction_path and instruction_path.is_file():
                expected_hashes["instruction"] = file_sha256(instruction_path)
        for name, section in (
            ("environment", spec.get("world")),
            ("generator", spec.get("generator")),
            ("verifier", spec.get("verifier")),
            ("reference_solution", spec.get("reference_solution")),
        ):
            if isinstance(section, dict):
                implementation = safe_path(
                    root,
                    section.get("implementation"),
                    findings,
                    f"run report {name} hash source",
                )
                if implementation and implementation.exists():
                    expected_hashes[name] = tree_sha256(implementation)
        findings.require(
            run.get("hashes") == expected_hashes,
            "run report hashes must exactly match the current instruction, "
            "objective contract, environment, generator, verifier, and reference solution",
        )
        command_rows = run.get("commands")
        findings.require(
            isinstance(command_rows, list), "run report commands must be a list"
        )
        passed: set[str] = set()
        execution_ids: list[str] = []
        for row in command_rows or []:
            if not isinstance(row, dict):
                findings.errors.append("every run report command row must be an object")
                continue
            name = row.get("name")
            row_valid = (
                isinstance(name, str)
                and name in COMMANDS
                and row.get("exit_code") == 0
                and isinstance(spec.get("commands"), dict)
                and row.get("command") == spec["commands"].get(name)
            )
            execution_id = row.get("execution_id")
            findings.require(
                non_empty_text(execution_id),
                f"run report command {name} execution_id must be non-empty",
            )
            if isinstance(execution_id, str):
                execution_ids.append(execution_id)
            started = parse_timestamp(row.get("started_at"))
            finished = parse_timestamp(row.get("finished_at"))
            findings.require(
                started is not None and finished is not None and finished >= started,
                f"run report command {name} needs ordered timezone-aware timestamps",
            )
            row_valid = row_valid and started is not None and finished is not None
            for stream in ("stdout", "stderr"):
                log_path = safe_path(
                    root,
                    row.get(f"{stream}_path"),
                    findings,
                    f"run report command {name} {stream}_path",
                )
                digest = row.get(f"{stream}_sha256")
                findings.require(
                    isinstance(digest, str) and SHA256.fullmatch(digest) is not None,
                    f"run report command {name} {stream}_sha256 must be a SHA-256 digest",
                )
                matches = bool(
                    log_path
                    and log_path.is_file()
                    and isinstance(digest, str)
                    and SHA256.fullmatch(digest)
                    and file_sha256(log_path) == digest
                )
                findings.require(
                    matches,
                    f"run report command {name} {stream} evidence hash must match",
                )
                row_valid = row_valid and matches
            if row_valid and isinstance(name, str):
                passed.add(name)
        findings.require(
            len(execution_ids) == len(set(execution_ids)),
            "run report command execution IDs must be distinct",
        )
        findings.require(
            COMMANDS <= passed,
            "run report must record every declared command verbatim with exit code 0 "
            "and valid execution evidence",
        )

    for name in ("threat_model", "known_limitations"):
        path = paths.get(name)
        if path and path.is_file():
            try:
                content = path.read_text()
            except (OSError, UnicodeDecodeError) as exc:
                findings.errors.append(f"cannot read artifacts.{name}: {exc}")
                continue
            findings.require(
                bool(content.strip()),
                f"artifacts.{name} must not be empty",
            )
            findings.require(
                PLACEHOLDER.search(content) is None,
                f"artifacts.{name} contains a placeholder",
            )


def validate_package(root: Path) -> list[str]:
    findings = Findings()
    spec_path = root / "task-spec.json"
    spec = load_json(spec_path, findings)
    if not isinstance(spec, dict):
        return findings.errors

    findings.require(
        set(spec) == TOP_LEVEL,
        f"task-spec.json keys must be exactly: {', '.join(sorted(TOP_LEVEL))}",
    )
    findings.require(spec.get("schema_version") == "1.0", "schema_version must be 1.0")
    findings.require(spec.get("status") == "ready", "status must be ready")
    task_id = spec.get("task_id")
    findings.require(
        isinstance(task_id, str) and ID.fullmatch(task_id) is not None,
        "task_id must be a stable lowercase identifier",
    )
    findings.require(
        isinstance(spec.get("task_version"), str)
        and bool(spec["task_version"].strip()),
        "task_version must be non-empty",
    )
    purpose = spec.get("purpose")
    findings.require(isinstance(purpose, dict), "purpose must be an object")
    if isinstance(purpose, dict):
        findings.require(
            purpose.get("origin") == "ground-up",
            "purpose.origin must be ground-up",
        )
        findings.require(
            purpose.get("benchmark_derivation") is False,
            "purpose.benchmark_derivation must be false",
        )
        for field in ("author_principal", "capability_claim", "counterfactual"):
            findings.require(
                non_empty_text(purpose.get(field)),
                f"purpose.{field} must be non-empty",
            )
        findings.require(
            isinstance(purpose.get("non_goals"), list),
            "purpose.non_goals must be a list",
        )

    found = placeholders(spec)
    findings.require(not found, f"placeholders remain at: {', '.join(found[:20])}")

    instruction = spec.get("instruction")
    findings.require(isinstance(instruction, dict), "instruction must be an object")
    if isinstance(instruction, dict):
        instruction_path = safe_path(
            root, instruction.get("path"), findings, "instruction.path"
        )
        digest = instruction.get("sha256")
        findings.require(
            isinstance(digest, str) and SHA256.fullmatch(digest) is not None,
            "instruction.sha256 must be a lowercase SHA-256 digest",
        )
        if (
            instruction_path
            and instruction_path.is_file()
            and SHA256.fullmatch(str(digest))
        ):
            try:
                instruction_text = instruction_path.read_text()
            except (OSError, UnicodeDecodeError) as exc:
                findings.errors.append(f"cannot read instruction.path: {exc}")
                instruction_text = ""
            findings.require(
                file_sha256(instruction_path) == digest,
                "instruction.sha256 does not match instruction.path",
            )
            findings.require(
                PLACEHOLDER.search(instruction_text) is None,
                "instruction.path contains a placeholder",
            )
        review = instruction.get("ambiguity_review")
        findings.require(
            isinstance(review, dict)
            and review.get("status") == "pass"
            and isinstance(review.get("reviewers"), list)
            and len(review["reviewers"]) >= 2,
            "ambiguity review must pass with at least two reviewers",
        )
        if isinstance(review, dict):
            reviewers = review.get("reviewers")
            valid_reviewers = (
                [reviewer for reviewer in reviewers if isinstance(reviewer, str)]
                if isinstance(reviewers, list)
                else []
            )
            findings.require(
                isinstance(reviewers, list)
                and len(valid_reviewers) == len(reviewers)
                and len(set(valid_reviewers)) >= 2
                and all(non_empty_text(reviewer) for reviewer in valid_reviewers),
                "ambiguity review needs at least two distinct reviewer IDs",
            )
            findings.require(
                review.get("agreement") == "unanimous",
                "ambiguity review agreement must be unanimous",
            )
            review_path = safe_path(
                root,
                review.get("evidence"),
                findings,
                "instruction.ambiguity_review.evidence",
            )
            evidence = (
                load_json(review_path, findings)
                if review_path and review_path.exists()
                else None
            )
            if isinstance(evidence, dict):
                findings.require(
                    evidence.get("status") == "pass",
                    "ambiguity review evidence status must be pass",
                )
                findings.require(
                    evidence.get("instruction_sha256") == digest,
                    "ambiguity review evidence must reference the current instruction hash",
                )
                evidence_reviewers = evidence.get("reviewers")
                purpose = spec.get("purpose")
                author_principal = (
                    purpose.get("author_principal")
                    if isinstance(purpose, dict)
                    else None
                )
                evidence_reviewer_ids = validate_independent_reviewers(
                    evidence_reviewers,
                    author_principal,
                    findings,
                    "ambiguity review evidence",
                )
                valid_evidence_reviewers = (
                    [row for row in evidence_reviewers if isinstance(row, dict)]
                    if isinstance(evidence_reviewers, list)
                    else []
                )
                findings.require(
                    evidence_reviewer_ids == set(valid_reviewers)
                    and all(
                        isinstance(row.get("required_write_set"), list)
                        for row in valid_evidence_reviewers
                    ),
                    "ambiguity review evidence must contain each independent reviewer "
                    "and their required_write_set",
                )
                findings.require(
                    evidence.get("unresolved_disagreements") == [],
                    "ambiguity review must have no unresolved disagreements",
                )

    requirement_ids = validate_requirements(spec, findings)
    validate_roles(root, spec, findings)

    world = spec.get("world")
    findings.require(
        isinstance(world, dict) and world.get("deterministic_replay") is True,
        "world.deterministic_replay must be true",
    )
    if isinstance(world, dict):
        safe_path(root, world.get("implementation"), findings, "world.implementation")
        findings.require(
            world.get("agent_isolation") in {"process", "container", "virtual-machine"},
            "world.agent_isolation must be process, container, or virtual-machine",
        )
        findings.require(
            world.get("secret_absent_from_agent_namespace") is True,
            "world.secret_absent_from_agent_namespace must be true",
        )
        safe_path(
            root,
            world.get("security_boundary_test"),
            findings,
            "world.security_boundary_test",
        )
    generator = spec.get("generator")
    findings.require(
        isinstance(generator, dict) and generator.get("records_rejections") is True,
        "generator.records_rejections must be true",
    )
    if isinstance(generator, dict):
        safe_path(
            root,
            generator.get("implementation"),
            findings,
            "generator.implementation",
        )
    verifier = spec.get("verifier")
    if isinstance(verifier, dict):
        safe_path(
            root,
            verifier.get("implementation"),
            findings,
            "verifier.implementation",
        )
        for key in (
            "independent_from_generator",
            "terminal_state_primary",
            "checks_forbidden_side_effects",
        ):
            findings.require(verifier.get(key) is True, f"verifier.{key} must be true")
        findings.require(
            verifier.get("critical_mutation_kill_rate") == 1.0,
            "verifier.critical_mutation_kill_rate must be 1.0",
        )
        rate = verifier.get("overall_mutation_kill_rate")
        findings.require(
            isinstance(rate, (int, float)) and rate >= 0.95,
            "verifier.overall_mutation_kill_rate must be at least 0.95",
        )
        if verifier.get("subjective_component") is True:
            human = verifier.get("human_validation")
            findings.require(
                isinstance(human, dict)
                and human.get("status") == "pass"
                and human.get("reviewers", 0) >= 2,
                "subjective verifier components need passing validation by at least two reviewers",
            )
    else:
        findings.errors.append("verifier must be an object")

    reference = spec.get("reference_solution")
    findings.require(
        isinstance(reference, dict)
        and reference.get("independent_from_verifier") is True,
        "reference_solution.independent_from_verifier must be true",
    )
    if isinstance(reference, dict):
        safe_path(
            root,
            reference.get("implementation"),
            findings,
            "reference_solution.implementation",
        )

    commands = spec.get("commands")
    findings.require(isinstance(commands, dict), "commands must be an object")
    if isinstance(commands, dict):
        findings.require(
            set(commands) == COMMANDS,
            f"commands keys must be exactly: {', '.join(sorted(COMMANDS))}",
        )
        for name, command in commands.items():
            findings.require(
                isinstance(command, str) and bool(command.strip()),
                f"commands.{name} must be non-empty",
            )
    for launcher in ("run.sh", "validate.sh"):
        path = safe_path(root, launcher, findings, launcher)
        findings.require(
            bool(path and path.is_file() and path.stat().st_mode & 0o111),
            f"{launcher} must be an executable file",
        )

    acceptance = spec.get("acceptance")
    findings.require(isinstance(acceptance, dict), "acceptance must be an object")
    if isinstance(acceptance, dict):
        findings.require(
            set(acceptance) == ACCEPTANCE,
            f"acceptance keys must be exactly: {', '.join(sorted(ACCEPTANCE))}",
        )
        for gate in ACCEPTANCE:
            findings.require(
                acceptance.get(gate) is True,
                f"acceptance.{gate} must be true",
            )

    validate_evidence(root, spec, requirement_ids, findings)
    return findings.errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a ground-up multi-agent task package and its audit evidence."
    )
    parser.add_argument("task_directory", type=Path)
    args = parser.parse_args()
    root = args.task_directory.resolve()
    if not root.is_dir():
        print(f"BLOCKED: task directory does not exist: {root}", file=sys.stderr)
        return 2
    try:
        errors = validate_package(root)
    except Exception as exc:
        print(
            f"BLOCKED: validator could not inspect the package: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2
    if errors:
        print(f"QUARANTINED: {len(errors)} release gate(s) failed", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"READY: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
