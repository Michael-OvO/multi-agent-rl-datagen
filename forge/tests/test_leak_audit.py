import json
import py_compile

from forge.maf.dimensions.scheduling import DIM as SCHED
from forge.maf.harbor import write_task
from forge.maf.leak_audit import audit, image_files, unparsed_copies


def _task_with_dockerfile(tmp_path, dockerfile_body, files=None):
    """Build a minimal task_dir (environment/Dockerfile + optional source files)
    without going through write_task, so COPY-parsing edge cases can be tested
    in isolation from the real dimension templates."""
    task_dir = tmp_path / "task"
    env = task_dir / "environment"
    env.mkdir(parents=True)
    for rel, content in (files or {}).items():
        p = env / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    (env / "Dockerfile").write_text(dockerfile_body)
    return task_dir


def test_image_files_follows_dockerfile_copy(tmp_path):
    inst = SCHED.generate(3, {"n": 6, "k": 2, "trap": True})
    d = write_task(SCHED, inst, tmp_path, "0001")
    names = {p.name for p in image_files(d)}
    # task.json is COPYed in; the Dockerfile itself is build context, not image.
    assert "task.json" in names
    assert "Dockerfile" not in names
    # Task 3 relocated the dimension module to tests/lib/, which Harbor
    # uploads only at verification time. The real task's Dockerfile no
    # longer COPYs a directory into the agent image at all.
    assert "maf_dim.py" not in names


def test_image_files_expands_directory_copy(tmp_path):
    # Directory-expansion coverage, now synthetic since the real task's
    # Dockerfile no longer COPYs a directory into the agent image (see
    # test_image_files_follows_dockerfile_copy above). Pinned independently
    # of test_scheduling_task_does_not_leak so this parser capability stays
    # covered on its own merits.
    d = _task_with_dockerfile(
        tmp_path,
        "FROM python:3.11-slim\nCOPY lib /app/lib\n",
        {"lib/maf_dim.py": "ORACLE = 1\ndef verify(x):\n    pass\n"},
    )
    names = {p.name for p in image_files(d)}
    assert "maf_dim.py" in names


def test_scheduling_task_does_not_leak(tmp_path):
    inst = SCHED.generate(3, {"n": 6, "k": 2, "trap": True})
    d = write_task(SCHED, inst, tmp_path, "0001")
    assert audit(d) == []


def test_image_files_handles_chown_flag(tmp_path):
    d = _task_with_dockerfile(
        tmp_path,
        "FROM python:3.11-slim\nCOPY --chown=1000:1000 task.json /app/task.json\n",
        {"task.json": "{}"},
    )
    names = {p.name for p in image_files(d)}
    assert names == {"task.json"}
    assert unparsed_copies(d) == []


def test_image_files_handles_multi_source(tmp_path):
    d = _task_with_dockerfile(
        tmp_path,
        "FROM python:3.11-slim\nCOPY a.txt b.txt dest/\n",
        {"a.txt": "a", "b.txt": "b"},
    )
    names = {p.name for p in image_files(d)}
    assert names == {"a.txt", "b.txt"}
    assert unparsed_copies(d) == []


def test_image_files_expands_glob(tmp_path):
    d = _task_with_dockerfile(
        tmp_path,
        "FROM python:3.11-slim\nCOPY *.py /app/\n",
        {"one.py": "print(1)", "two.py": "print(2)", "readme.txt": "hi"},
    )
    names = {p.name for p in image_files(d)}
    assert names == {"one.py", "two.py"}
    assert unparsed_copies(d) == []


def test_unresolvable_source_is_reported_not_dropped(tmp_path):
    d = _task_with_dockerfile(
        tmp_path,
        "FROM python:3.11-slim\nCOPY does-not-exist.txt /app/does-not-exist.txt\n",
    )
    # The old parser would silently drop this line. The new one must never
    # claim a clean scan of an image it didn't actually inspect.
    assert image_files(d) == []
    unresolved = unparsed_copies(d)
    assert len(unresolved) == 1
    assert "does-not-exist.txt" in unresolved[0]


def test_from_stage_copy_is_reported_not_dropped(tmp_path):
    d = _task_with_dockerfile(
        tmp_path,
        "FROM python:3.11-slim\nCOPY --from=builder /src/app /app/app\n",
    )
    assert image_files(d) == []
    assert len(unparsed_copies(d)) == 1


def test_audit_surfaces_unparsed_copy_as_violation(tmp_path):
    d = _task_with_dockerfile(
        tmp_path,
        "FROM python:3.11-slim\nCOPY --from=builder /src/app /app/app\n",
    )
    violations = audit(d)
    assert len(violations) == 1
    assert "not fully inspected" in violations[0] or "unresolved" in violations[0].lower()


def test_audit_clean_when_all_copies_resolve(tmp_path):
    d = _task_with_dockerfile(
        tmp_path,
        "FROM python:3.11-slim\nCOPY task.json /app/task.json\n",
        {"task.json": "{}"},
    )
    assert audit(d) == []


# --- Review findings ------------------------------------------------------
#
# Each test below reproduces a way the physical-line COPY parser let a file
# into the agent image without the audit ever seeing it. Reverting the
# corresponding fix must turn the test red again.


def test_backslash_continuation_source_is_scanned(tmp_path):
    # Finding 1 (CRITICAL): a source on a continuation line is invisible to a
    # parser that walks physical lines -- it never reaches image_files() or
    # unparsed_copies(), so audit() reports clean on an image it never
    # actually inspected. This is the exact Dockerfile from the finding.
    d = _task_with_dockerfile(
        tmp_path,
        "FROM python:3.11-slim\n"
        "COPY a.py \\\n"
        "     leak_secret.py \\\n"
        "     /app/dest/\n",
        {
            "a.py": "print('a')\n",
            "leak_secret.py": "ORACLE = 1\ndef verify(x):\n    pass\n",
        },
    )
    names = {p.name for p in image_files(d)}
    assert "leak_secret.py" in names
    violations = audit(d)
    assert violations != []
    assert any("leak_secret.py" in v for v in violations)


def test_traversal_source_is_a_violation_not_silently_included(tmp_path):
    # Finding 2 (IMPORTANT): `../../secret_outside.txt` is lexically inside
    # task_dir's prefix (so `f.relative_to(task_dir)` never raises) but
    # physically outside `environment/`. The audit must neither read this
    # file into the image nor silently drop the COPY line -- it must report
    # the line as unresolved.
    (tmp_path / "secret_outside.txt").write_text("ORACLE outside the task dir\n")
    d = _task_with_dockerfile(
        tmp_path,
        "FROM python:3.11-slim\nCOPY ../../secret_outside.txt /app/secret.txt\n",
    )
    assert not any(f.name == "secret_outside.txt" for f in image_files(d))
    unresolved = unparsed_copies(d)
    assert len(unresolved) == 1
    assert audit(d) != []


def test_add_directive_is_recognized_like_copy(tmp_path):
    # Finding 3 (IMPORTANT): the parser only matched COPY. ADD also copies
    # files into the image -- an ADD directive was silently skipped, the
    # same silent-drop bug as Finding 1.
    d = _task_with_dockerfile(
        tmp_path,
        "FROM python:3.11-slim\nADD lib /app/lib\n",
        {"lib/leak.py": "ORACLE = 1\ndef verify(x):\n    pass\n"},
    )
    names = {p.name for p in image_files(d)}
    assert "leak.py" in names
    assert audit(d) != []


def test_add_url_source_is_unresolved_not_silently_skipped(tmp_path):
    # Companion to Finding 3: ADD also accepts a URL, which is not a local
    # path at all. That must fail closed into unparsed_copies(), not vanish
    # the way an unrecognized directive would.
    d = _task_with_dockerfile(
        tmp_path,
        "FROM python:3.11-slim\nADD https://example.com/archive.tar.gz /app/archive.tar.gz\n",
    )
    assert image_files(d) == []
    assert len(unparsed_copies(d)) == 1


# --- Third-round review findings ------------------------------------------
#
# The previous fix (0119e3d) introduced _logical_lines() to join backslash
# continuations, but joined ANY physical line ending in `\`, including
# comment lines -- reintroducing the exact silent-drop bug class it was
# meant to close, just via a `#` line instead of a plain COPY line.


def test_comment_ending_in_backslash_does_not_swallow_next_line(tmp_path):
    # Finding 1 (CRITICAL): a `#` line is a full-line comment. Docker does
    # not continue comments -- a trailing `\` inside one is a literal
    # backslash, not a continuation marker. The previous fix's
    # _logical_lines() joined it anyway, splicing the comment together with
    # the COPY line that follows into one unmatched logical line, so the
    # COPY (and its source) vanished from both image_files() and
    # unparsed_copies(). This is the exact Dockerfile from the finding.
    d = _task_with_dockerfile(
        tmp_path,
        "FROM python:3.11-slim\n"
        "# note: path uses backslash \\\n"
        "COPY leak_secret.py /app/dest/\n",
        {"leak_secret.py": "ORACLE = 1\ndef verify(x):\n    pass\n"},
    )
    assert image_files(d) != []
    assert unparsed_copies(d) == []
    violations = audit(d)
    assert violations != []
    assert any("leak_secret.py" in v for v in violations)


def test_plain_comment_does_not_swallow_following_copy(tmp_path):
    # Regression, pinning the other direction: an ordinary comment with no
    # trailing backslash must keep behaving exactly like before -- it must
    # not swallow (or otherwise disturb) the COPY line after it.
    d = _task_with_dockerfile(
        tmp_path,
        "FROM python:3.11-slim\n"
        "# just a plain comment, no continuation\n"
        "COPY task.json /app/task.json\n",
        {"task.json": "{}"},
    )
    names = {p.name for p in image_files(d)}
    assert names == {"task.json"}
    assert unparsed_copies(d) == []
    assert audit(d) == []


def test_add_local_archive_is_unresolved_not_scanned_as_opaque_file(tmp_path):
    # Finding 2 (IMPORTANT): ADD auto-extracts a local archive at the
    # destination -- its contents are not one opaque file, they're whatever
    # the archive contains, none of which the audit can see (the marker
    # scan is blind on compressed bytes, and _ground_truth_keys only looks
    # at `.json` files). The audit must say it could not inspect this
    # rather than silently scan the compressed blob and call it clean.
    d = _task_with_dockerfile(
        tmp_path,
        "FROM python:3.11-slim\nADD leak.tar.gz /app/\n",
        {"leak.tar.gz": "not real gzip bytes, just needs to exist on disk"},
    )
    assert not any(f.name == "leak.tar.gz" for f in image_files(d))
    unresolved = unparsed_copies(d)
    assert len(unresolved) == 1
    assert "leak.tar.gz" in unresolved[0]
    assert audit(d) != []


# --- G1 fail-open: compiled bytecode is invisible to the audit ------------
#
# `_SKIP_SUFFIXES = (".pyc",)` filtered compiled bytecode out of
# image_files() before the marker/ground-truth scan ever ran. Verified
# facts (see task report): every FORBIDDEN_MARKERS substring survives into
# compiled bytecode; a module imports and runs from a .pyc alone with no
# .py source anywhere on disk (copy maf_core.pyc + maf_dim.pyc onto
# sys.path -- ORACLE is present, generate() is callable); and the checked-in
# tasks/parallel-scheduling-0003/environment/ actually ships lib/__pycache__
# *.pyc via a `COPY lib /app/lib` Dockerfile line, so this is a real path,
# not a theoretical one. "I cannot scan this" must fail closed into a
# violation, not a silent skip.


def test_pyc_only_lib_dir_is_a_violation(tmp_path):
    # (a) A lib/ dir COPYed into the image that holds ONLY compiled
    # bytecode -- no .py source at all -- must not audit clean. This is the
    # exact shape of the exploit: an agent needs no .py anywhere to import
    # and run the module.
    d = _task_with_dockerfile(
        tmp_path,
        "FROM python:3.11-slim\nCOPY lib /app/lib\n",
    )
    lib = d / "environment" / "lib"
    pycache = lib / "__pycache__"
    pycache.mkdir(parents=True)
    src = tmp_path / "maf_dim_src.py"
    src.write_text("ORACLE = 1\ndef verify(x):\n    pass\n")
    py_compile.compile(
        str(src), cfile=str(pycache / "maf_dim.cpython-313.pyc"), doraise=True
    )
    # Confirm the fixture matches the claim: bytecode only, no .py under lib/.
    assert not any(p.suffix == ".py" for p in lib.rglob("*"))
    assert audit(d) != []


def test_pyc_alongside_py_violation_names_pyc_not_only_py(tmp_path):
    # (b) A .pyc sitting next to its already-flagged .py must be named in
    # its own violation. Flagging only the .py would still miss the exploit
    # path this module exists to close: an agent can import from the .pyc
    # even when the .py is also visible to the scan.
    d = _task_with_dockerfile(
        tmp_path,
        "FROM python:3.11-slim\nCOPY lib /app/lib\n",
        {"lib/maf_dim.py": "ORACLE = 1\ndef verify(x):\n    pass\n"},
    )
    lib = d / "environment" / "lib"
    pycache = lib / "__pycache__"
    pycache.mkdir(parents=True)
    py_compile.compile(
        str(lib / "maf_dim.py"),
        cfile=str(pycache / "maf_dim.cpython-313.pyc"),
        doraise=True,
    )
    violations = audit(d)
    assert violations != []
    assert any("maf_dim.cpython-313.pyc" in v for v in violations), violations


def test_image_files_includes_compiled_bytecode(tmp_path):
    # image_files() itself must stop hiding .pyc -- it is a file genuinely
    # copied into the agent image, and downstream consumers (Tasks 3, 5, 7)
    # rely on image_files() to see everything that lands there.
    d = _task_with_dockerfile(
        tmp_path,
        "FROM python:3.11-slim\nCOPY lib /app/lib\n",
    )
    lib = d / "environment" / "lib"
    lib.mkdir(parents=True, exist_ok=True)
    (lib / "module.pyc").write_bytes(b"\x00\x01\x02\xf3\xfe\xff\x00")
    names = {p.name for p in image_files(d)}
    assert "module.pyc" in names


# --- Final-review finding 1: ground-truth detection was unfalsifiable -----
#
# Verified during the final review: replacing _ground_truth_keys()'s body
# with `return []` -- disabling ground-truth detection outright -- left the
# suite byte-identical at 70 passed, 2 xfailed. Sabotaging the marker scan
# by contrast turned 3 tests red. NO test anywhere asserted that audit()
# can report a `_`-key violation at all, and the one test that used to
# assert `_planted`/`_opt_makespan` explicitly had been rewritten to
# delegate to this unpinned detector -- the original sin reborn inside its
# own replacement.
#
# Every test in this section must go red when _ground_truth_keys() stops
# detecting. That is the check that exposed the gap; it is now the check
# that keeps it closed.


def test_toplevel_ground_truth_key_is_a_violation(tmp_path):
    # The floor: a `_`-key in a JSON the Dockerfile COPYs into the agent
    # image must produce a violation that names the key.
    d = _task_with_dockerfile(
        tmp_path,
        "FROM python:3.11-slim\nCOPY task.json /app/task.json\n",
        {
            "task.json": json.dumps(
                {"workers": {"w0": ["test"]}, "_opt_makespan": 7}
            )
        },
    )
    violations = audit(d)
    assert violations != []
    assert any("_opt_makespan" in v for v in violations), violations


def test_every_ground_truth_key_is_named_not_just_the_first(tmp_path):
    # Scheduling's real ground truth is two keys. Reporting only one would
    # leave the other invisible to a reader triaging the violation list.
    d = _task_with_dockerfile(
        tmp_path,
        "FROM python:3.11-slim\nCOPY task.json /app/task.json\n",
        {
            "task.json": json.dumps(
                {"subtasks": {}, "_planted": [], "_opt_makespan": 7}
            )
        },
    )
    violations = audit(d)
    assert any("_planted" in v for v in violations), violations
    assert any("_opt_makespan" in v for v in violations), violations


def test_ground_truth_violation_names_the_file(tmp_path):
    # A violation that does not say which file it came from cannot be acted
    # on when a task ships several JSONs.
    d = _task_with_dockerfile(
        tmp_path,
        "FROM python:3.11-slim\nCOPY data /app/data\n",
        {
            "data/clean.json": json.dumps({"workers": {}}),
            "data/leaky.json": json.dumps({"_planted": [1]}),
        },
    )
    gt = [v for v in audit(d) if "_planted" in v]
    assert len(gt) == 1, audit(d)
    assert "leaky.json" in gt[0], gt


def test_public_only_json_has_no_ground_truth_violation(tmp_path):
    # The other direction: the scanner must not cry wolf on nested *public*
    # data, or the signal it produces is worthless.
    d = _task_with_dockerfile(
        tmp_path,
        "FROM python:3.11-slim\nCOPY task.json /app/task.json\n",
        {
            "task.json": json.dumps(
                {
                    "workers": {"w0": ["test", "code"], "w1": ["code"]},
                    "subtasks": {"t000": {"skill": "code", "dur": 3, "deps": []}},
                }
            )
        },
    )
    assert audit(d) == []


# --- Final-review finding 2: the scanner disobeyed its own doctrine -------
#
# The module docstring promises that any file it cannot decode is surfaced
# as a violation, and audit()'s docstring promised "no ground-truth key ...
# in any file". The scanner's actual scope was far narrower: no TOP-LEVEL
# `_`-key in a parseable `.json` dict. Each shape below returned
# `audit() == []` -- a clean bill of health on ground truth sitting in the
# agent's image.
#
# `forge.maf.core.public()` strips only top-level `_` keys too, so producer
# and checker shared the identical blind spot: the checker structurally
# could not catch the producer's most likely regression. These tests pin
# the checker's half of that (core.public() is deliberately untouched).


def test_nested_ground_truth_key_is_a_violation(tmp_path):
    # A `_`-key one level down is exactly as readable to the agent as a
    # top-level one -- `json.load(...)["nested"]["_culprit"]`.
    d = _task_with_dockerfile(
        tmp_path,
        "FROM python:3.11-slim\nCOPY task.json /app/task.json\n",
        {"task.json": json.dumps({"pub": 1, "nested": {"_culprit": "w3"}})},
    )
    violations = audit(d)
    assert violations != []
    assert any("_culprit" in v for v in violations), violations


def test_deeply_nested_ground_truth_key_inside_a_list_is_a_violation(tmp_path):
    # Recursion must cross list boundaries too, not just dict values.
    d = _task_with_dockerfile(
        tmp_path,
        "FROM python:3.11-slim\nCOPY task.json /app/task.json\n",
        {"task.json": json.dumps({"steps": [{"ok": 1}, {"_answer": [{"_x": 2}]}]})},
    )
    violations = audit(d)
    assert any("_answer" in v for v in violations), violations
    assert any("_x" in v for v in violations), violations


def test_toplevel_json_list_ground_truth_key_is_a_violation(tmp_path):
    # `isinstance(data, dict)` was the gate: a JSON document whose root is a
    # list audited clean no matter what it held.
    d = _task_with_dockerfile(
        tmp_path,
        "FROM python:3.11-slim\nCOPY task.json /app/task.json\n",
        {"task.json": json.dumps([{"_culprit": "w3"}])},
    )
    violations = audit(d)
    assert violations != []
    assert any("_culprit" in v for v in violations), violations


def test_jsonl_ground_truth_key_is_a_violation(tmp_path):
    # The `.json` suffix gate: ground truth shipped as a `.jsonl` transcript
    # (one document per line -- the shape the interactive dimensions use)
    # was never looked at.
    d = _task_with_dockerfile(
        tmp_path,
        "FROM python:3.11-slim\nCOPY truth.jsonl /app/truth.jsonl\n",
        {
            "truth.jsonl": '{"turn": 1, "public": "hi"}\n'
            '{"turn": 2, "_culprit": "w3"}\n'
        },
    )
    violations = audit(d)
    assert violations != []
    assert any("_culprit" in v for v in violations), violations


def test_clean_jsonl_is_not_a_false_positive(tmp_path):
    d = _task_with_dockerfile(
        tmp_path,
        "FROM python:3.11-slim\nCOPY log.jsonl /app/log.jsonl\n",
        {"log.jsonl": '{"turn": 1}\n\n{"turn": 2}\n'},
    )
    assert audit(d) == []


def test_unparseable_json_is_a_violation_not_a_silent_skip(tmp_path):
    # `except Exception: return []` was a literal silent skip, in a module
    # whose docstring says "I cannot scan this" must never be treated as
    # "therefore harmless". A `.json` the scanner cannot parse is a file it
    # did not inspect.
    d = _task_with_dockerfile(
        tmp_path,
        "FROM python:3.11-slim\nCOPY task.json /app/task.json\n",
        {"task.json": '{"_planted": [1, 2,'},  # truncated: not valid JSON
    )
    assert audit(d) != []


def test_unparseable_jsonl_line_is_a_violation_not_a_silent_skip(tmp_path):
    d = _task_with_dockerfile(
        tmp_path,
        "FROM python:3.11-slim\nCOPY truth.jsonl /app/truth.jsonl\n",
        {"truth.jsonl": '{"turn": 1}\nnot json at all\n'},
    )
    assert audit(d) != []
