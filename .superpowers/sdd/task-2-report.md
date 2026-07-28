# Task 2 report: Leak audit (G1)

Branch: `fix/isolation-and-gates`
Base: `e8db524` (Task 1, docs retraction)

## What was built

### `forge/maf/leak_audit.py` (new)

Used verbatim from the brief. Two public functions:

- `image_files(task_dir: Path) -> list[Path]` — parses `environment/Dockerfile`
  line by line, picks out `COPY <src> <dst>` directives, resolves `<src>`
  relative to `environment/` (matching how `forge/maf/harbor.py:_write_static`
  emits `COPY task.json /app/task.json` / `COPY lib /app/lib`), and expands
  directories recursively. `.pyc` files are excluded. Deliberately reads the
  Dockerfile rather than walking the whole rendered task directory, so files
  that are build context only (e.g. a future `docker-compose.yaml` holding a
  verifier token) are never considered "in the image."
- `_ground_truth_keys(path)` — for `.json` files, returns any top-level dict
  keys starting with `_` (the convention `forge/maf/harbor.py` uses to split
  public vs. ground-truth fields via `public(instance)` /
  `{k: v for k, v in instance.items() if k.startswith("_")}`).
- `audit(task_dir: Path) -> list[str]` — runs `image_files()`, then for each
  file: flags any ground-truth JSON keys, and does a substring scan for
  `FORBIDDEN_MARKERS = ("def generate(", "ORACLE", "CHEATERS", "def verify(",
  "def ablate(", "DIFFICULTY_PRESETS")`. Empty return means clean.

Full file content matches the brief exactly (copied verbatim, no changes).

### `forge/tests/test_leak_audit.py` (new)

Two tests, verbatim from the brief:

- `test_image_files_follows_dockerfile_copy` — asserts `image_files()` includes
  `task.json` and excludes `Dockerfile` itself for a rendered scheduling task.
- `test_scheduling_task_does_not_leak` — asserts `audit(d) == []` for a
  rendered scheduling task. Marked
  `@pytest.mark.xfail(reason="leak open until Task 3 relocates the dimension
  module", strict=True)` per Step 4, with `import pytest` added at the top of
  the file.

## Step 3: observed red-test failure (before adding xfail)

Ran `.venv/bin/python -m pytest forge/tests/test_leak_audit.py -vv` with the
xfail marker *not yet applied*. Result: `test_image_files_follows_dockerfile_copy`
PASSED; `test_scheduling_task_does_not_leak` FAILED as expected. Exact
violation list `audit(d)` returned (12 items, in order):

```
environment/lib/maf_dim.py: grading machinery 'def generate(' in agent image
environment/lib/maf_dim.py: grading machinery 'ORACLE' in agent image
environment/lib/maf_dim.py: grading machinery 'CHEATERS' in agent image
environment/lib/maf_dim.py: grading machinery 'def verify(' in agent image
environment/lib/maf_dim.py: grading machinery 'def ablate(' in agent image
environment/lib/maf_dim.py: grading machinery 'DIFFICULTY_PRESETS' in agent image
environment/lib/maf_core.py: grading machinery 'def generate(' in agent image
environment/lib/maf_core.py: grading machinery 'ORACLE' in agent image
environment/lib/maf_core.py: grading machinery 'CHEATERS' in agent image
environment/lib/maf_core.py: grading machinery 'def verify(' in agent image
environment/lib/maf_core.py: grading machinery 'def ablate(' in agent image
environment/lib/maf_core.py: grading machinery 'DIFFICULTY_PRESETS' in agent image
```

**Deviation from the brief's Step 3 prediction, noted rather than corrected:**
the brief expected violations "for `environment/lib/maf_dim.py`" only (6
markers). The actual list has 12 — the same 6 markers additionally fire on
`environment/lib/maf_core.py`. Reason: `forge/maf/harbor.py:_copy_runtime`
copies `forge/maf/core.py` into `environment/lib/maf_core.py` unconditionally
(same as `maf_dim.py`, and this is also `COPY lib /app/lib`-ed into the image
per the Dockerfile), and `forge/maf/core.py` defines the `Dimension` protocol
whose docstring/abstract-method text contains the literal substrings `ORACLE`,
`CHEATERS`, `DIFFICULTY_PRESETS`, `def generate(`, `def verify(`, and
`def ablate(` (as field/method declarations, not the dimension-specific
implementations, but the marker scan is substring-based and doesn't
distinguish). This is a real, correctly-detected instance of grading-adjacent
machinery reaching the agent image — `maf_core.py` is shipped into `/app/lib`
alongside `maf_dim.py` — so I did not treat it as a false positive or adjust
`image_files()`/`FORBIDDEN_MARKERS` to suppress it. I flagged it verbatim as
observed. No ground-truth JSON keys (`_planted`, `_opt_makespan`, etc.) were
found in `task.json`, since `harbor.py` already strips `_`-prefixed keys via
`public()` before writing that file — the leak here is entirely the
copied-module route, matching the brief's exploit narrative.

## Step 4: xfail marker + suite state after

`.venv/bin/python -m pytest forge/tests/test_leak_audit.py -v`:

```
forge/tests/test_leak_audit.py::test_image_files_follows_dockerfile_copy PASSED
forge/tests/test_leak_audit.py::test_scheduling_task_does_not_leak XFAIL
1 passed, 1 xfailed in 0.03s
```

Full suite, `.venv/bin/python -m pytest`:

```
42 passed, 1 xfailed in 0.11s
```

No pre-existing test regressed. Checked `pyproject.toml`'s
`[tool.pytest.ini_options]` for any `xfail_strict` global setting that could
interact with the per-test `strict=True` — none present, so the marker's
explicit `strict=True` is the only thing enforcing "this must stay red until
Task 3 flips it, or the suite fails."

## Commit

```
git add forge/maf/leak_audit.py forge/tests/test_leak_audit.py
git commit -m "test(g1): leak audit reproduces the seed-brute-force exploit

audit() reads the agent Dockerfile's COPY directives and reports any
grading machinery or ground-truth key reachable by the agent. Currently
xfail-strict for scheduling: environment/lib/maf_dim.py ships generate(),
which is seed-deterministic and therefore reconstructs /tests content."
```

## Things I was unsure about / flagging for reviewer

1. **12 violations vs. the brief's implied 6.** Covered above in detail. I
   judged this as "the audit is working as designed, and additionally caught a
   second leaking file the brief's author may not have had in mind when
   writing the Step 3 prediction" rather than a bug in my `image_files()`. The
   brief's own ambiguity-resolution note told me to investigate rather than
   adjust the test if the *pass/fail* outcome were wrong (it wasn't — it did
   fail), so I did not touch the marker list or `image_files()` to narrow the
   result down to 6. Task 3 (which relocates the dimension module out of the
   agent image) will need to also stop shipping `maf_core.py` verbatim, or
   this audit will still fail after Task 3's fix.
2. I did not modify `forge/maf/harbor.py`, `forge/maf/core.py`, or
   `forge/maf/dimensions/scheduling.py` — Task 2 is detector-only, per the
   brief ("Do not fix it here — Task 3 fixes it.").
3. Left `sources/` and other pre-existing untracked files in the working tree
   untouched (unrelated to this task; present before I started).

---

## Follow-up: review-finding fix (2026-07-14)

A reviewer flagged one **Important** defect in the `leak_audit.py` above:
`image_files()`'s `COPY` parser assumed `parts[1]` was the only source, so it
silently dropped (returned fewer files for) any `--chown=`/`--from=` flag
form, multi-source `COPY a b dest/`, and glob sources like `COPY *.py /app/`
— none of those forms appear in today's two Dockerfile templates, but the
failure mode (audit reports "clean" on an image it never actually looked at)
is exactly the kind of false assurance this module exists to prevent. A
**Minor** finding also asked to pin the directory-expansion branch (`COPY lib
/app/lib` pulling `maf_dim.py` in) independently of the xfail'd leak test.

### What changed

**`forge/maf/leak_audit.py`**

- Added a third public function, `unparsed_copies(task_dir) -> list[str]`,
  with the exact docstring specified in the finding. It returns the raw text
  of every `COPY` line that couldn't be confidently resolved to real host
  paths.
- Introduced `_scan()`, a private helper both `image_files()` and
  `unparsed_copies()` now call, so there's a single parse pass and no risk of
  the two functions disagreeing about which lines were resolved.
- Introduced `_resolve_copy(args, env)` and `_resolve_source(token, env)`:
  - Leading `--flag` / `--flag=value` tokens are skipped (handles
    `--chown=`, `--chmod=`, etc.).
  - `--from=stage` unconditionally marks the whole directive unresolved —
    its content is another build stage's output, never something on host
    disk, so no amount of matching-by-name would be honest.
  - Every token except the last is treated as a source (multi-source
    `COPY a b dest/` now resolves both `a` and `b`).
  - Sources containing glob metacharacters (`*`, `?`, `[`) are expanded via
    `Path.glob()` against `environment/`; directories among the hits are
    further expanded via `rglob`.
  - **Fail-closed rule:** any source — literal or glob — that matches no
    file or directory on disk makes the *entire* `COPY` line unresolved
    (not partially resolved), which covers heredoc (`COPY <<EOF dest`) and
    JSON-array (`COPY ["a", "b"]`) forms for free: their tokens never match
    real paths, so they fall through to "unresolved" without any special
    parsing.
  - Source tokens are normalized with `token.lstrip("/")` before joining to
    `environment/`, to avoid pathlib's `Path("/env") / "/abs"` == `Path("/abs")`
    trap silently escaping to the real filesystem root on an absolute-looking
    source token.
- `audit()` now calls `unparsed_copies()` first and appends one violation per
  entry — `"COPY directive not fully inspected (image may contain unaudited
  content): <line>"` — before scanning `image_files()`. An audit that hits an
  unparseable `COPY` line can never again report `[]` ("clean") without the
  reader seeing that the image wasn't actually inspected.
- `image_files()` still returns `list[Path]`, `audit()` still returns
  `list[str]` — signatures Tasks 3/5/7 depend on are unchanged.
- Did not touch `forge/maf/harbor.py` (Task 3's file) or weaken/remove
  `test_scheduling_task_does_not_leak`'s `xfail(strict=True)` — that leak is
  still real and still Task 3's to fix.

**`forge/tests/test_leak_audit.py`**

Wrote the new tests first, confirmed they failed (import error, since
`unparsed_copies` didn't exist yet), then implemented:

- `test_image_files_follows_dockerfile_copy` — added
  `assert "maf_dim.py" in names`, pinning directory expansion (Finding 2)
  independently of the xfail'd leak test.
- `test_image_files_handles_chown_flag` — `COPY --chown=1000:1000 task.json
  /app/task.json` resolves to `task.json`, no unparsed lines.
- `test_image_files_handles_multi_source` — `COPY a.txt b.txt dest/` resolves
  both `a.txt` and `b.txt`.
- `test_image_files_expands_glob` — `COPY *.py /app/` resolves only the `.py`
  files present, ignores `readme.txt`.
- `test_unresolvable_source_is_reported_not_dropped` — a `COPY` of a
  nonexistent file yields `image_files() == []` **and**
  `len(unparsed_copies(d)) == 1`, with the missing filename in the message —
  proves the line is surfaced, not silently dropped.
- `test_from_stage_copy_is_reported_not_dropped` — `COPY --from=builder
  /src/app /app/app` is always unresolved, regardless of what exists on disk.
- `test_audit_surfaces_unparsed_copy_as_violation` — `audit()` on a
  `--from=` directive returns exactly one violation mentioning
  "not fully inspected" / "unresolved".
- `test_audit_clean_when_all_copies_resolve` — a fully-resolvable `COPY`
  still yields `audit(d) == []`, so the new fail-closed path doesn't produce
  false positives on ordinary directives.
- Added a `_task_with_dockerfile(tmp_path, dockerfile_body, files=None)` test
  helper that builds a minimal `environment/Dockerfile` (plus optional source
  files) without going through `write_task`, to exercise `COPY`-parsing edge
  cases independent of the real dimension templates.

### Test command and results

Red (before implementing, `unparsed_copies` not yet defined):

```
$ .venv/bin/python -m pytest forge/tests/test_leak_audit.py -v
ImportError: cannot import name 'unparsed_copies' from 'forge.maf.leak_audit'
1 error in 0.05s
```

Green (after implementing):

```
$ .venv/bin/python -m pytest forge/tests/test_leak_audit.py -v
forge/tests/test_leak_audit.py::test_image_files_follows_dockerfile_copy PASSED
forge/tests/test_leak_audit.py::test_scheduling_task_does_not_leak XFAIL
forge/tests/test_leak_audit.py::test_image_files_handles_chown_flag PASSED
forge/tests/test_leak_audit.py::test_image_files_handles_multi_source PASSED
forge/tests/test_leak_audit.py::test_image_files_expands_glob PASSED
forge/tests/test_leak_audit.py::test_unresolvable_source_is_reported_not_dropped PASSED
forge/tests/test_leak_audit.py::test_from_stage_copy_is_reported_not_dropped PASSED
forge/tests/test_leak_audit.py::test_audit_surfaces_unparsed_copy_as_violation PASSED
forge/tests/test_leak_audit.py::test_audit_clean_when_all_copies_resolve PASSED
8 passed, 1 xfailed in 0.03s
```

Full suite, unchanged pass count plus the new coverage:

```
$ .venv/bin/python -m pytest -q
49 passed, 1 xfailed in 0.12s
```

`test_scheduling_task_does_not_leak` remains `xfail(strict=True)` and still
xfails for the same reason as before (`maf_dim.py`/`maf_core.py` shipped
verbatim into `/app/lib`) — untouched by this fix.

### Commit

```
1fac2bd fix(g1): fail closed on unparseable Dockerfile COPY directives
```

`forge/maf/leak_audit.py` and `forge/tests/test_leak_audit.py` only;
`forge/maf/harbor.py` not modified.

### Concerns / things to flag

- The fail-closed rule treats "glob matches zero files" the same as "typo'd
  literal filename" — both become an `unparsed_copies` violation rather than
  a silent no-op. This is intentional (per the finding's own framing: "a
  source that matches no file or directory on disk"), but it does mean a
  Dockerfile with e.g. `COPY *.md /app/docs/` in a directory with no
  markdown files would trip the audit even though nothing leaks. I judged
  this an acceptable false positive given the fail-closed mandate — it's
  loud and requires a human look, which is the intended failure mode.
- Per source token (not per `COPY` line) would be a finer-grained
  alternative for the multi-source partial-failure case (e.g. `COPY a
  missing.txt dest/` where `a` resolves but `missing.txt` doesn't) — I chose
  to fail the whole line closed rather than partially report `a`, so a
  partially-bad line doesn't get a partial pass. Flagging this design choice
  in case Task 3/5/7 want per-token granularity instead.

---

## Fix report: review findings on the leak audit (2026-07-14)

Branch: `fix/isolation-and-gates`. Fixes three findings against
`forge/maf/leak_audit.py` from the code review of commit `1fac2bd`.

### Finding 1 (CRITICAL): backslash continuation lines silently dropped

`_scan()` walked physical lines via `dockerfile.read_text().splitlines()`. A
source token on a continuation line (`COPY a.py \` / `     leak_secret.py \`
/ `     /app/dest/`) was on a physical line whose first token was
`leak_secret.py`, not `COPY` — the line was skipped outright, so the file
never reached `image_files()` or `unparsed_copies()`. Reproduced exactly:
`audit()` returned `[]` for a Dockerfile shipping a file containing `ORACLE`
and `def verify(`.

**Fix:** added `_logical_lines(text)`, an explicit pre-pass that joins any
physical line ending in a bare trailing backslash with the line that
follows (stripping the backslash, keeping the rest), before any directive
matching or source resolution happens. `_scan()` now iterates
`_logical_lines(dockerfile.read_text())` instead of `.splitlines()`. Every
later stage only ever sees one complete logical directive per line, so
there is no separate continuation-aware branch to keep in sync with the
resolver.

### Finding 2 (IMPORTANT): `..` traversal not clamped to `environment/`

`_resolve_source()` built `target = env / rel` and never checked whether
`..` components in the source token walked the result back out of
`environment/`. Because the traversal is only lexical (`f.relative_to
(task_dir)` in `audit()` still succeeds — the string starts with the right
prefix even though `..` later cancels it out), such a file would be
silently included in `image_files()` and read/scanned by `audit()`.

**Fix:** added `_clamped(path, root)`, which resolves both `path` and `root`
(`Path.resolve()`, which normalizes `..` without requiring the target to
exist) and returns `None` if the resolved path is not `root` itself and
`root` is not one of its parents. `_resolve_source()` now calls
`_clamped(target, env)` (and, for the glob branch, `_clamped(hit, env)` per
match) and treats a clamp failure exactly like any other unresolvable
source — it makes the whole `COPY`/`ADD` line unparsed, not a silent
skip and not a silent include.

### Finding 3 (IMPORTANT): `ADD` not recognized

`_scan()` matched only `parts[0].upper() == "COPY"`; an `ADD lib /app/lib`
line's first token is `ADD`, so the whole directive was skipped — the same
silent-drop failure mode as Finding 1, just via a different directive
keyword.

**Fix:** added `_DIRECTIVES = ("COPY", "ADD")` and changed the match to
`parts[0].upper() not in _DIRECTIVES`. `ADD`'s source(s) go through the same
`_resolve_copy` / `_resolve_source` path as `COPY`, so a local file/dir ADD
is scanned identically. A URL source (`ADD https://.../archive.tar.gz ...`)
is not a real path under `environment/`; `_resolve_source` already returns
`None` for it via the ordinary "matches nothing on disk" case (no special
URL-detection code needed), so it lands in `unparsed_copies()` — fail-closed,
not silently skipped the way it was when `ADD` wasn't recognized at all.

### Tests added (all written before the fix, confirmed red, confirmed green after)

`forge/tests/test_leak_audit.py`, appended under a `# --- Review findings
---` section:

- `test_backslash_continuation_source_is_scanned` — the exact Dockerfile
  from Finding 1 (`COPY a.py \` / continuation / `/app/dest/`), source file
  containing `ORACLE` and `def verify(`. Asserts `leak_secret.py` is in
  `image_files()` and `audit()` is non-empty and mentions the file.
- `test_traversal_source_is_a_violation_not_silently_included` — a
  `COPY ../../secret_outside.txt /app/secret.txt` directive with a real file
  two levels above `environment/`. Asserts the file never appears in
  `image_files()`, that `unparsed_copies()` reports exactly one entry, and
  that `audit()` is non-empty.
- `test_add_directive_is_recognized_like_copy` — `ADD lib /app/lib` with
  `lib/leak.py` containing `ORACLE`/`def verify(`. Asserts `leak.py` is in
  `image_files()` and `audit()` is non-empty.
- `test_add_url_source_is_unresolved_not_silently_skipped` — companion
  coverage for the `ADD`-with-URL case: asserts `image_files()` is empty and
  `unparsed_copies()` has exactly one entry (0 before the fix, since an
  unrecognized `ADD` directive was skipped with no `unparsed` entry either).

Verified each of the four new tests fails for the right reason against the
pre-fix module (`git show HEAD:forge/maf/leak_audit.py` swapped in
temporarily, then restored) before implementing the fix, and again as a
final check after implementing it — all four failed, then all four passed,
with no other test's outcome changing.

`test_scheduling_task_does_not_leak` is untouched and still
`xfail(strict=True)`: harbor.py's real Dockerfile template
(`COPY task.json /app/task.json` / `COPY lib /app/lib`) has no continuation
lines, no traversal, and no `ADD`, so none of these three fixes touch its
outcome — it still xfails for the pre-existing `maf_dim.py`/`maf_core.py`
leak that Task 3 owns.

### Test run

```
$ .venv/bin/python -m pytest forge/tests/test_leak_audit.py -v
...
forge/tests/test_leak_audit.py::test_image_files_follows_dockerfile_copy PASSED
forge/tests/test_leak_audit.py::test_scheduling_task_does_not_leak XFAIL
forge/tests/test_leak_audit.py::test_image_files_handles_chown_flag PASSED
forge/tests/test_leak_audit.py::test_image_files_handles_multi_source PASSED
forge/tests/test_leak_audit.py::test_image_files_expands_glob PASSED
forge/tests/test_leak_audit.py::test_unresolvable_source_is_reported_not_dropped PASSED
forge/tests/test_leak_audit.py::test_from_stage_copy_is_reported_not_dropped PASSED
forge/tests/test_leak_audit.py::test_audit_surfaces_unparsed_copy_as_violation PASSED
forge/tests/test_leak_audit.py::test_audit_clean_when_all_copies_resolve PASSED
forge/tests/test_leak_audit.py::test_backslash_continuation_source_is_scanned PASSED
forge/tests/test_leak_audit.py::test_traversal_source_is_a_violation_not_silently_included PASSED
forge/tests/test_leak_audit.py::test_add_directive_is_recognized_like_copy PASSED
forge/tests/test_leak_audit.py::test_add_url_source_is_unresolved_not_silently_skipped PASSED
12 passed, 1 xfailed in 0.04s
```

Full suite:

```
$ .venv/bin/python -m pytest -q
53 passed, 1 xfailed in 0.12s
```

(Was `49 passed, 1 xfailed` before this pass; +4 for the new tests, no
regressions.)

### Commit

`forge/maf/leak_audit.py` and `forge/tests/test_leak_audit.py` only.
`forge/maf/harbor.py` not modified.

### Concerns / things to flag

- `_logical_lines` joins with a single space and does not special-case an
  escaped literal backslash (`\\` at end of line meaning "a real backslash
  character", vs. a line-continuation backslash). Real Dockerfiles don't
  put a trailing backslash at end of a `COPY`/`ADD` line for any reason
  other than continuation, so this wasn't treated as in-scope.
- The traversal clamp uses `Path.resolve()`, which follows symlinks. A
  symlink placed inside `environment/` that points outside it would resolve
  to a target outside `root` and correctly get clamped (treated as
  unresolvable) — this is arguably *more* fail-closed than the finding
  strictly asked for (which was about lexical `..` tokens), but it's the
  same helper and the same failure mode, so I didn't special-case it out.
- Per Finding 3's own note, `ADD` also auto-extracts local tar archives at
  the destination. If a `.tar.gz` file resolves as a real local file, it is
  treated as an ordinary single-file copy (the same as before this fix) —
  the audit does not open the archive and scan its contents. That's an
  existing limitation of the marker/JSON-key scan (it never inspects inside
  any archive format), not something this pass introduced or was asked to
  fix; flagging it in case a future task wants archive-aware scanning.

---

## Final fix round (2026-07-14): comment-swallowed-continuation + ADD archive

Third round on `forge/maf/leak_audit.py`. Each of the first two rounds' fixes
introduced a new instance of the same bug class (silent under-report instead
of fail-closed); this round closes the two remaining review findings and
rewrites the module docstring so the audit is honest about what it actually
guarantees.

### Finding 1 (CRITICAL): comment lines swallowed the line after them

`_logical_lines()` (added in `0119e3d`) joined **any** physical line ending
in `\`, including comment (`#`) lines. Real Docker does not continue
comments — a trailing `\` in a `#` line is a literal backslash, not a
continuation marker. Reproduced exactly per the finding:

```
FROM python:3.11-slim
# note: path uses backslash \
COPY leak_secret.py /app/dest/
```

with `leak_secret.py` containing `ORACLE = 1` / `def verify(x): pass`. Before
the fix: `image_files() == []`, `unparsed_copies() == []`, `audit() == []` —
completely clean, while the file shipped into the image untouched.

**Fix:** `_logical_lines()` now strips every line whose stripped form starts
with `#` *before* doing continuation-joining, matching Docker's own parse
order. A comment can therefore no longer eat the line that follows it,
whether or not the comment itself ends in `\`.

### Finding 2 (IMPORTANT): `ADD` of a local archive scanned as one opaque file

`ADD leak.tar.gz /app/` resolved as an ordinary single-file copy. `ADD`
auto-extracts local archives at the destination, so the image actually gets
whatever the archive *contains* — the marker scan is blind on compressed
bytes, and `_ground_truth_keys()` only inspects `.json` files. Content could
land in the image with the audit never having looked at it.

**Fix (no archive extraction implemented, as instructed):** added
`_ARCHIVE_SUFFIXES = (".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tar.xz",
".zip")`. `_resolve_copy()` now takes the directive name; when the directive
is `ADD` and a source token ends in one of these suffixes, the whole
directive is treated as unresolvable — the same fail-closed path as a
`--from=` multi-stage copy — so it surfaces via `unparsed_copies()` and
`audit()` rather than being read and scanned as if it were plain text.
Scoped to `ADD` only (not `COPY`), per the finding: `COPY` never extracts, so
a `COPY` of a `.tar.gz` is an existing, out-of-scope, general "binary file"
limitation of the marker scan, not the extraction-specific issue this
finding is about.

### Docstring rewrite

Replaced the module docstring per the brief's "Framing" section: it now
states plainly (1) what the module does — a static approximation of Docker's
COPY/ADD build semantics over the Dockerfile templates `forge/maf/harbor.py`
generates, (2) the fail-closed principle and why (a silent under-report is
false assurance, worse than no audit), (3) the known limitation that it does
not build the image and can only approximate, so anything unresolved is
surfaced as a violation rather than assumed safe, and (4) the precise scope
of its guarantee — clean for the Dockerfile forms `harbor.py` emits today;
unfamiliar forms fail closed rather than getting the benefit of the doubt.

### Tests (`forge/tests/test_leak_audit.py`)

Added under a new `# --- Third-round review findings ---` section, written
first and confirmed red against the pre-fix module:

- `test_comment_ending_in_backslash_does_not_swallow_next_line` — the exact
  Dockerfile from Finding 1. Asserts `image_files()` is non-empty,
  `unparsed_copies() == []`, and `audit()` is non-empty and mentions
  `leak_secret.py`.
- `test_plain_comment_does_not_swallow_following_copy` — regression pinning
  the *other* direction: an ordinary comment with no trailing backslash must
  not disturb the `COPY` line after it (`image_files()` still resolves
  `task.json`, `audit() == []`). This test already passed before the fix
  (it isn't a new failure mode) — added per the brief's explicit instruction
  to pin both directions.
- `test_add_local_archive_is_unresolved_not_scanned_as_opaque_file` —
  `ADD leak.tar.gz /app/` with a real (dummy-content) `leak.tar.gz` file
  present. Asserts the archive is absent from `image_files()`, appears
  exactly once in `unparsed_copies()` by name, and `audit()` is non-empty.

Red run (new tests against the pre-fix module, docstring already updated but
`_logical_lines`/`_resolve_copy` not yet):

```
$ .venv/bin/python -m pytest forge/tests/test_leak_audit.py -k "comment or archive" -v
forge/tests/test_leak_audit.py::test_comment_ending_in_backslash_does_not_swallow_next_line FAILED
forge/tests/test_leak_audit.py::test_plain_comment_does_not_swallow_following_copy PASSED
forge/tests/test_leak_audit.py::test_add_local_archive_is_unresolved_not_scanned_as_opaque_file FAILED
2 failed, 1 passed, 13 deselected in 0.04s
```

Green run (after implementing both fixes):

```
$ .venv/bin/python -m pytest forge/tests/test_leak_audit.py -v
forge/tests/test_leak_audit.py::test_image_files_follows_dockerfile_copy PASSED
forge/tests/test_leak_audit.py::test_scheduling_task_does_not_leak XFAIL
forge/tests/test_leak_audit.py::test_image_files_handles_chown_flag PASSED
forge/tests/test_leak_audit.py::test_image_files_handles_multi_source PASSED
forge/tests/test_leak_audit.py::test_image_files_expands_glob PASSED
forge/tests/test_leak_audit.py::test_unresolvable_source_is_reported_not_dropped PASSED
forge/tests/test_leak_audit.py::test_from_stage_copy_is_reported_not_dropped PASSED
forge/tests/test_leak_audit.py::test_audit_surfaces_unparsed_copy_as_violation PASSED
forge/tests/test_leak_audit.py::test_audit_clean_when_all_copies_resolve PASSED
forge/tests/test_leak_audit.py::test_backslash_continuation_source_is_scanned PASSED
forge/tests/test_leak_audit.py::test_traversal_source_is_a_violation_not_silently_included PASSED
forge/tests/test_leak_audit.py::test_add_directive_is_recognized_like_copy PASSED
forge/tests/test_leak_audit.py::test_add_url_source_is_unresolved_not_silently_skipped PASSED
forge/tests/test_leak_audit.py::test_comment_ending_in_backslash_does_not_swallow_next_line PASSED
forge/tests/test_leak_audit.py::test_plain_comment_does_not_swallow_following_copy PASSED
forge/tests/test_leak_audit.py::test_add_local_archive_is_unresolved_not_scanned_as_opaque_file PASSED
15 passed, 1 xfailed in 0.04s
```

Full suite:

```
$ .venv/bin/python -m pytest -q
56 passed, 1 xfailed in 0.12s
```

(Was `53 passed, 1 xfailed` before this round; +3 new tests, no regressions.)
`test_scheduling_task_does_not_leak` remains `xfail(strict=True)`, untouched
— `harbor.py`'s real Dockerfile template has no comments and no `ADD`, so
neither fix changes its outcome; it still xfails for the pre-existing
`maf_dim.py`/`maf_core.py` leak that Task 3 owns.

### Commit

```
910e471 fix(g1): stop comments from eating continuations; fail closed on ADD archives
```

`forge/maf/leak_audit.py` and `forge/tests/test_leak_audit.py` only.
`forge/maf/harbor.py` not modified.

### Concerns / things to flag

- The archive-suffix check is scoped to `ADD` only, matching the finding's
  own framing. A `COPY` of a `.tar.gz` still resolves as an ordinary opaque
  file and gets the same blind marker scan as any other binary file — that
  is a pre-existing, general, out-of-scope limitation (the marker/JSON-key
  scan can't see inside *any* non-text format, archive or otherwise), not
  something specific to this finding.
- `_ARCHIVE_SUFFIXES` matches by literal suffix (`token.endswith(...)`), so
  it also fires on glob sources like `ADD *.tar.gz /app/` before any glob
  expansion happens — intentional, since expanding first would still leave
  every hit an archive needing the same rejection.
- Comment-stripping is a straight `raw.lstrip().startswith("#")` check, so a
  continuation line whose *middle* — not first — physical line is a comment
  (e.g. `COPY a \` / `# comment` / `b dest/`) has the comment line removed
  entirely and the continuation still joins `COPY a` to `b dest/` across it.
  This isn't a form the finding described or `harbor.py` emits; flagging it
  as an edge case in case a future round wants stricter handling (e.g.
  treating an in-continuation comment line as terminating the directive
  instead of being transparently skipped).
  fix; flagging it in case a future task wants archive-aware scanning.
