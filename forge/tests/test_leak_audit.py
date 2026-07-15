import pytest

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
    # COPY lib /app/lib pulls the whole lib dir in via directory expansion --
    # that's the exact leak this audit exists to catch. Pin it independently of
    # the xfail'd leak test below, so directory expansion stays covered even
    # while the leak itself remains open.
    assert "maf_dim.py" in names


@pytest.mark.xfail(reason="leak open until Task 3 relocates the dimension module", strict=True)
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
