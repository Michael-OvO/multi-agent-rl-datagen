"""G1: assert the agent's image contains nothing that derives ground truth.

The audit reads the agent service's Dockerfile COPY directives to decide what
actually lands in the image. Scanning the rendered directory instead would
produce false positives on build-context files (compose files, sidecar
Dockerfiles) that the agent never sees.

Rationale for each marker: shipping generate() lets the agent brute-force the
seed until the public fields match and then read the private ones out of its own
regenerated instance -- which defeats /tests isolation entirely. Shipping ORACLE
lets it execute the reference solution. Shipping verify() lets it read the
grader. All three were executed against the shipped tasks on 2026-07-14.
"""

from __future__ import annotations

import json
from pathlib import Path

# Substrings that must never appear in a file the agent can read.
FORBIDDEN_MARKERS = (
    "def generate(",
    "ORACLE",
    "CHEATERS",
    "def verify(",
    "def ablate(",
    "DIFFICULTY_PRESETS",
)

_SKIP_SUFFIXES = (".pyc",)


def image_files(task_dir: Path) -> list[Path]:
    """Host paths of files copied into the agent image by its Dockerfile."""
    task_dir = Path(task_dir)
    env = task_dir / "environment"
    dockerfile = env / "Dockerfile"
    if not dockerfile.exists():
        return []
    out: list[Path] = []
    for line in dockerfile.read_text().splitlines():
        parts = line.split()
        if len(parts) < 3 or parts[0].upper() != "COPY":
            continue
        src = env / parts[1]
        if src.is_dir():
            out.extend(p for p in src.rglob("*") if p.is_file())
        elif src.is_file():
            out.append(src)
    return [p for p in out if p.suffix not in _SKIP_SUFFIXES]


def _ground_truth_keys(path: Path) -> list[str]:
    if path.suffix != ".json":
        return []
    try:
        data = json.loads(path.read_text())
    except Exception:
        return []
    if not isinstance(data, dict):
        return []
    return [k for k in data if k.startswith("_")]


def audit(task_dir: Path) -> list[str]:
    """Return violations. Empty means the agent image derives no ground truth."""
    task_dir = Path(task_dir)
    violations: list[str] = []
    for f in image_files(task_dir):
        rel = f.relative_to(task_dir)
        for key in _ground_truth_keys(f):
            violations.append(f"{rel}: ground-truth key {key!r} in agent image")
        try:
            text = f.read_text(errors="ignore")
        except Exception:
            continue
        for marker in FORBIDDEN_MARKERS:
            if marker in text:
                violations.append(f"{rel}: grading machinery {marker!r} in agent image")
    return violations
