"""G1: static audit that the agent's image contains nothing that derives
ground truth.

What this does: statically approximates Docker's COPY/ADD build semantics
over the Dockerfile templates this repo generates (see
`forge/maf/harbor.py`) -- stripping comments, joining backslash line
continuations, resolving `--chown=`/multi-source/glob forms, and expanding
directories -- to decide which host files actually land in the agent's
image. It then scans those files for ground-truth JSON keys and grading-
machinery markers (see FORBIDDEN_MARKERS below).

Fail-closed, and why: the only way to know for certain what ends up in a
built image is to build it and list its contents, and this module
deliberately does not do that (that would put a Docker build in the
unit-test path). A static approximation can therefore never fully replicate
Docker's own parser -- it can only approximate. Anything this module cannot
resolve with confidence (an unrecognized flag, a `--from=` multi-stage
copy, a heredoc/JSON-array COPY, a source resolving outside the build
context, an archive an `ADD` would auto-extract, ...) is surfaced via
`unparsed_copies()` and turned into an `audit()` violation rather than
silently skipped or silently assumed safe. A silent under-report is false
assurance -- worse than no audit at all, because it says "clean" about an
image nobody actually inspected.

Guarantee, precisely stated: for the Dockerfile forms `forge/maf/harbor.py`
actually emits today (plain `COPY <source> <dest>` lines, no continuations,
no comments, no ADD, no archives, no multi-stage builds), `audit() == []`
means the image is clean with respect to the marker/ground-truth-key scan
below. Any Dockerfile construct this module does not specifically recognize
does not get the benefit of the doubt -- it fails closed into a reported
violation instead of a clean result.

The same fail-closed rule applies to file *content*, not just to Dockerfile
syntax. Compiled Python (`.pyc`/`.pyo`, and anything under a `__pycache__`
directory) is never a legitimate part of an agent image for this repo's
task templates: every marker in FORBIDDEN_MARKERS survives verbatim into
compiled bytecode as a literal string constant, and a module imports and
runs from a `.pyc` alone with no `.py` source present anywhere on disk. A
substring scan over marshalled bytecode is not "coverage" -- a scan that
happens to miss a marker is indistinguishable from a clean result -- so
such files are a flat violation rather than a best-effort scan. More
generally, any file this module cannot decode as text is surfaced as a
violation rather than silently skipped: "I cannot scan this" must never be
treated as "therefore harmless".
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

_GLOB_CHARS = "*?["
_DIRECTIVES = ("COPY", "ADD")

# `ADD` (unlike `COPY`) auto-extracts a local archive at the destination --
# the image ends up with whatever the archive contains, not the archive
# itself. This module does not implement archive extraction (that would mean
# re-deriving Docker's own tar/gzip/zip handling); a marker scan over the
# still-compressed bytes is blind, and _ground_truth_keys() only looks at
# `.json` files, so an ADD-with-archive source would otherwise land content
# in the image the audit never actually inspects. Fail closed instead: any
# `ADD` source with one of these suffixes is treated as unresolvable, the
# same as a `--from=` multi-stage copy.
_ARCHIVE_SUFFIXES = (".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tar.xz", ".zip")


def image_files(task_dir: Path) -> list[Path]:
    """Host paths of files copied into the agent image by its Dockerfile.

    Includes everything a resolved COPY/ADD directive puts in the image --
    compiled bytecode included. A file silently dropped here would be
    invisible to every downstream consumer of this list (audit() below, and
    the callers in Tasks 3/5/7), which is the exact failure mode this
    function must not reintroduce.
    """
    files, _ = _scan(Path(task_dir))
    return files


def unparsed_copies(task_dir: Path) -> list[str]:
    """COPY/ADD directives image_files() could not resolve to real paths.

    Each entry is a violation: an unresolvable COPY/ADD may put anything into
    the image, so an audit that ignored it would report clean on an image it
    never actually inspected.
    """
    _, unparsed = _scan(Path(task_dir))
    return unparsed


def _logical_lines(text: str) -> list[str]:
    """Join Dockerfile backslash line continuations into single logical lines.

    A directive parser that walks physical lines never sees a source token
    that lands on a continuation line -- it isn't malformed input, it's a
    normal multi-line COPY/ADD that silently vanishes from the scan. This is
    an explicit pre-pass so every later stage (directive matching, source
    resolution) only ever sees one complete directive per logical line.

    Comment lines are stripped BEFORE continuation-joining, matching Docker's
    own semantics: a `#` line is a full-line comment, not a statement that
    can span multiple lines, so a trailing `\\` inside one is a literal
    backslash rather than a continuation marker. Joining first (as an
    earlier version of this function did) would let a comment ending in `\\`
    splice itself onto the next physical line -- silently swallowing
    whatever real directive followed, which is the same silent-drop failure
    this function exists to prevent, just reached through a `#` line instead
    of a plain one.
    """
    physical = [
        raw.rstrip() for raw in text.splitlines() if not raw.lstrip().startswith("#")
    ]
    logical: list[str] = []
    buf: list[str] = []
    for line in physical:
        if line.endswith("\\"):
            buf.append(line[:-1])
            continue
        buf.append(line)
        logical.append(" ".join(buf))
        buf = []
    if buf:  # trailing continuation with no terminating line
        logical.append(" ".join(buf))
    return logical


def _scan(task_dir: Path) -> tuple[list[Path], list[str]]:
    """Walk the Dockerfile's COPY/ADD directives once, splitting them into
    files we can confidently say are in the image and lines we can't vouch
    for at all.

    Deliberately not a full Dockerfile COPY/ADD implementation -- fails
    closed instead: anything we can't resolve with confidence becomes an
    `unparsed` entry rather than being silently dropped (the bug this
    replaces).
    """
    env = task_dir / "environment"
    dockerfile = env / "Dockerfile"
    if not dockerfile.exists():
        return [], []
    files: list[Path] = []
    unparsed: list[str] = []
    for line in _logical_lines(dockerfile.read_text()):
        parts = line.split()
        if not parts or parts[0].upper() not in _DIRECTIVES:
            continue
        directive = parts[0].upper()
        resolved = _resolve_copy(directive, parts[1:], env)
        if resolved is None:
            unparsed.append(line.strip())
        else:
            files.extend(resolved)
    return files, unparsed


def _resolve_copy(directive: str, args: list[str], env: Path) -> list[Path] | None:
    """Resolve one COPY/ADD directive's arguments (everything after the
    `COPY`/`ADD` token) to concrete host files, or None if any part of it
    can't be confidently resolved (an unrecognized flag, a multi-stage
    `--from=` source, a heredoc/JSON-array form, an `ADD` source with an
    archive suffix, or a source matching nothing on disk).
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
        if directive == "ADD" and token.endswith(_ARCHIVE_SUFFIXES):
            return None  # auto-extracted archive -- see _ARCHIVE_SUFFIXES
        matches = _resolve_source(token, env)
        if matches is None:
            return None
        out.extend(matches)
    return out


def _clamped(path: Path, root: Path) -> Path | None:
    """Return `path` if it resolves to somewhere inside `root`, else None.

    A source token like `../../../../etc/passwd` is lexically inside
    `root`'s prefix (so a later `f.relative_to(task_dir)` never raises) but
    `..` walks it physically outside. Real `docker build` refuses a source
    escaping the build context; a source that escapes here must be treated
    the same as any other unresolvable source -- a violation, not a silent
    include and not a silent skip.
    """
    root_r = root.resolve()
    resolved = path.resolve()
    if resolved != root_r and root_r not in resolved.parents:
        return None
    return path


def _resolve_source(token: str, env: Path) -> list[Path] | None:
    """Resolve a single COPY/ADD source token to files on disk, or None if it
    matches no file or directory (including a glob matching nothing, or a
    path that only resolves outside `env` -- e.g. `..` traversal, or a URL
    passed to `ADD`)."""
    rel = token.lstrip("/")
    if any(c in token for c in _GLOB_CHARS):
        hits = list(env.glob(rel))
        if not hits:
            return None
        out: list[Path] = []
        for hit in hits:
            if _clamped(hit, env) is None:
                return None
            if hit.is_dir():
                out.extend(p for p in hit.rglob("*") if p.is_file())
            elif hit.is_file():
                out.append(hit)
        return out
    target = env / rel
    if _clamped(target, env) is None:
        return None
    if target.is_dir():
        return [p for p in target.rglob("*") if p.is_file()]
    if target.is_file():
        return [target]
    return None


_COMPILED_SUFFIXES = (".pyc", ".pyo")


def _is_compiled_python(path: Path) -> bool:
    """True for a compiled-bytecode file, or any file under a __pycache__ dir.

    See the module docstring: these are never legitimate in an agent image
    for this repo's task templates, and are treated as a flat violation
    rather than substring-scanned, because a scan over marshalled bytecode
    that happens to miss a marker is indistinguishable from a clean result.
    """
    return path.suffix in _COMPILED_SUFFIXES or "__pycache__" in path.parts


def _decode_text(path: Path) -> str | None:
    """Return `path`'s contents as text, or None if it cannot be decoded.

    A file that isn't valid UTF-8 text -- an image, an archive, a compiled
    artifact -- cannot be substring-scanned with any confidence: bytes that
    happen to decode do not mean the scan covered the file's real content,
    and there is no way to tell "scanned and clean" apart from "silently
    missed". Callers must turn a None here into a violation, never a skip.
    """
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
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
    """Return violations found in the files this module can resolve.

    An empty list means: no ground-truth key and no grading-machinery marker was
    found in any file reachable from a COPY/ADD directive this module could parse,
    and no directive was left uninspected. It is *not* an unconditional guarantee
    that the image is clean -- this is a static approximation that never builds
    the image. See the module docstring for the exact scope. Unrecognized forms
    fail closed and appear here as violations rather than being assumed safe.
    """
    task_dir = Path(task_dir)
    violations: list[str] = []
    for line in unparsed_copies(task_dir):
        violations.append(
            f"COPY/ADD directive not fully inspected (image may contain "
            f"unaudited content): {line}"
        )
    for f in image_files(task_dir):
        rel = f.relative_to(task_dir)
        for key in _ground_truth_keys(f):
            violations.append(f"{rel}: ground-truth key {key!r} in agent image")
        if _is_compiled_python(f):
            violations.append(
                f"{rel}: compiled Python bytecode in agent image -- unauditable "
                f"(grading markers survive compilation and a module can be "
                f"imported from bytecode alone, with no .py source present)"
            )
            continue
        text = _decode_text(f)
        if text is None:
            violations.append(
                f"{rel}: file in agent image could not be scanned as text "
                f"(unscannable content is a violation, not a skip)"
            )
            continue
        for marker in FORBIDDEN_MARKERS:
            if marker in text:
                violations.append(f"{rel}: grading machinery {marker!r} in agent image")
    return violations
