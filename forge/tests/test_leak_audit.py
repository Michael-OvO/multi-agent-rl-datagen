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
