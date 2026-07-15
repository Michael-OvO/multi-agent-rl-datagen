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
_GLOB_CHARS = "*?["


def image_files(task_dir: Path) -> list[Path]:
    """Host paths of files copied into the agent image by its Dockerfile."""
    files, _ = _scan(Path(task_dir))
    return [p for p in files if p.suffix not in _SKIP_SUFFIXES]


def unparsed_copies(task_dir: Path) -> list[str]:
    """COPY directives image_files() could not resolve to real paths.

    Each entry is a violation: an unresolvable COPY may put anything into the
    image, so an audit that ignored it would report clean on an image it never
    actually inspected.
    """
    _, unparsed = _scan(Path(task_dir))
    return unparsed


def _scan(task_dir: Path) -> tuple[list[Path], list[str]]:
    """Walk the Dockerfile's COPY directives once, splitting them into files we
    can confidently say are in the image and lines we can't vouch for at all.

    Deliberately not a full Dockerfile COPY implementation -- fails closed
    instead: anything we can't resolve with confidence becomes an `unparsed`
    entry rather than being silently dropped (the bug this replaces).
    """
    env = task_dir / "environment"
    dockerfile = env / "Dockerfile"
    if not dockerfile.exists():
        return [], []
    files: list[Path] = []
    unparsed: list[str] = []
    for line in dockerfile.read_text().splitlines():
        parts = line.split()
        if not parts or parts[0].upper() != "COPY":
            continue
        resolved = _resolve_copy(parts[1:], env)
        if resolved is None:
            unparsed.append(line.strip())
        else:
            files.extend(resolved)
    return files, unparsed


def _resolve_copy(args: list[str], env: Path) -> list[Path] | None:
    """Resolve one COPY directive's arguments (everything after the `COPY`
    token) to concrete host files, or None if any part of it can't be
    confidently resolved (an unrecognized flag, a multi-stage `--from=`
    source, a heredoc/JSON-array form, or a source matching nothing on disk).
    """
    i = 0
    while i < len(args) and args[i].startswith("--"):
        if args[i].startswith("--from="):
            return None  # copies from another build stage, not the host disk
        i += 1
    rest = args[i:]
    if len(rest) < 2:
        return None  # not a recognizable "source(s)... dest" shape

    out: list[Path] = []
    for token in rest[:-1]:  # every token but the last is a source
        matches = _resolve_source(token, env)
        if matches is None:
            return None
        out.extend(matches)
    return out


def _resolve_source(token: str, env: Path) -> list[Path] | None:
    """Resolve a single COPY source token to files on disk, or None if it
    matches no file or directory (including a glob matching nothing)."""
    rel = token.lstrip("/")
    if any(c in token for c in _GLOB_CHARS):
        hits = list(env.glob(rel))
        if not hits:
            return None
        out: list[Path] = []
        for hit in hits:
            if hit.is_dir():
                out.extend(p for p in hit.rglob("*") if p.is_file())
            elif hit.is_file():
                out.append(hit)
        return out
    target = env / rel
    if target.is_dir():
        return [p for p in target.rglob("*") if p.is_file()]
    if target.is_file():
        return [target]
    return None


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
    for line in unparsed_copies(task_dir):
        violations.append(
            f"COPY directive not fully inspected (image may contain unaudited "
            f"content): {line}"
        )
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
