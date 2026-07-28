### Task 3: Relocate the dimension module out of the agent image

Static dimensions ship `maf_dim.py` to `tests/lib/` instead of `environment/lib/`. Harbor uploads `tests/` inside `verify()` (`harbor/verifier/verifier.py:147`), which runs after the agent phase, so the module is present for grading and absent during the agent's run.

**Files:**
- Modify: `forge/maf/harbor.py:29-53` (`write_task`), `:59-75` (`_write_static`), `:121-130` (`_copy_runtime`)
- Modify: `forge/maf/runtime/verify_entry.py:34` (`sys.path.insert`)
- Modify: `forge/tests/test_leak_audit.py` (drop the xfail)
- Modify: `forge/tests/test_harbor.py:23-30` (`test_public_files_hide_ground_truth`)

**Interfaces:**
- Consumes: `forge.maf.leak_audit.audit` (Task 2).
- Produces: `_copy_runtime(dim, lib_dir: Path, include_cli: bool)` — Plan 2 calls this with the sidecar's lib dir.

- [ ] **Step 1: Strengthen the harbor test that gave false assurance**

`test_public_files_hide_ground_truth` (`forge/tests/test_harbor.py:23`) promises a global property but only runs on scheduling and only checks `instruction.md` and `task.json`. It passed throughout the audit while three exploits were live. Replace it:

```python
from forge.maf.leak_audit import audit


def test_agent_image_hides_ground_truth_and_grader(tmp_path):
    inst = DIM.generate(2, {"n": 5, "k": 2, "trap": True})
    d = write_task(DIM, inst, tmp_path, "0001")
    assert audit(d) == []


def test_dimension_module_ships_to_tests_not_environment(tmp_path):
    inst = DIM.generate(2, {"n": 5, "k": 2, "trap": True})
    d = write_task(DIM, inst, tmp_path, "0001")
    assert (d / "tests" / "lib" / "maf_dim.py").exists()
    assert not (d / "environment" / "lib").exists()
```

- [ ] **Step 2: Run to verify both fail**

Run: `.venv/bin/python -m pytest forge/tests/test_harbor.py -v`

Expected: both new tests FAIL — `audit` returns violations, and `tests/lib/maf_dim.py` does not exist.

- [ ] **Step 3: Relocate the module in `harbor.py`**

In `write_task`, change the directory creation and the `_copy_runtime` call. Replace lines 29-36:

```python
def write_task(dim, instance: dict, out_dir, task_id: str) -> Path:
    task_dir = Path(out_dir) / f"{dim.NAME}-{task_id}"
    for sub in ("environment", "tests/lib", "solution"):
        (task_dir / sub).mkdir(parents=True, exist_ok=True)

    # The dimension module holds generate()/ORACLE/verify()/CHEATERS. It ships to
    # tests/, which Harbor uploads only at verification time -- never to the
    # agent's image. See docs/superpowers/specs/2026-07-14-outcome-based-sidecar-redesign.md
    _copy_runtime(dim, task_dir / "tests" / "lib", include_cli=dim.INTERACTIVE)
```

In `_write_static`, drop the `COPY lib /app/lib` line. Replace lines 62-64:

```python
    (task_dir / "environment" / "Dockerfile").write_text(
        _DOCKER_BASE + "COPY task.json /app/task.json\n"
    )
```

Update `_copy_runtime`'s signature (line 121):

```python
def _copy_runtime(dim, lib_dir: Path, include_cli: bool = False):
    import forge.maf.core as core_mod

    lib_dir.mkdir(parents=True, exist_ok=True)
    lib_dir.joinpath("maf_core.py").write_text(Path(core_mod.__file__).read_text())
    mod = importlib.import_module(type(dim).__module__)
    src = Path(mod.__file__).read_text()
    src = src.replace("from forge.maf.core import", "from maf_core import")
    lib_dir.joinpath("maf_dim.py").write_text(src)
    if include_cli:
        lib_dir.joinpath("cli.py").write_text((_RUNTIME / "cli.py").read_text())
```

- [ ] **Step 4: Point the in-container verifier at the new location**

In `forge/maf/runtime/verify_entry.py`, replace line 34 (`sys.path.insert(0, "/app/lib")`):

```python
    sys.path.insert(0, "/tests/lib")
```

- [ ] **Step 5: Remove the xfail from Task 2's test**

In `forge/tests/test_leak_audit.py`, delete the `@pytest.mark.xfail(...)` decorator and its `import pytest` if now unused.

- [ ] **Step 6: Run the full suite**

Run: `.venv/bin/python -m pytest forge/tests/ -v`

Expected: `test_agent_image_hides_ground_truth_and_grader`, `test_dimension_module_ships_to_tests_not_environment`, and `test_scheduling_task_does_not_leak` all PASS. Interactive-dimension tests still pass (they are in-process and do not render tasks).

- [ ] **Step 7: Prove the exploit is dead end-to-end**

Regenerate a scheduling task and confirm the seed brute-force can no longer run:

```bash
.venv/bin/python -m forge.forge_cli gen --dim parallel-scheduling --seed 3 --difficulty medium --out /tmp/leakcheck
ls /tmp/leakcheck/parallel-scheduling-0000/environment/
```

Expected: `Dockerfile` and `task.json` only. No `lib/`. The generator is not in the image, so there is nothing to brute-force.

- [ ] **Step 8: Commit**

```bash
git add forge/maf/harbor.py forge/maf/runtime/verify_entry.py forge/tests/test_harbor.py forge/tests/test_leak_audit.py
git commit -m "fix(isolation): ship the dimension module to tests/, not the agent image

Harbor uploads tests/ inside verifier.verify(), after the agent phase, so
the module is available for grading and absent during the agent's run.
Closes the seed-brute-force exploit (seed=3 recovered _planted -> 1.0).

Also replaces test_public_files_hide_ground_truth, which promised a global
property, ran only on scheduling, checked only two files, and stayed green
through three live exploits."
```

---

