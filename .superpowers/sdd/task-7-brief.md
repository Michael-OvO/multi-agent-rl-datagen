### Task 7: Regenerate scheduling tasks and verify end-to-end

The plan's claims are about generated artifacts, so verify against real ones rather than only unit tests.

**Files:**
- Modify: `tasks/parallel-scheduling-0003/**` (regenerated)

**Interfaces:**
- Consumes: everything above.
- Produces: nothing importable.

- [ ] **Step 1: Regenerate**

```bash
rm -rf tasks/parallel-scheduling-0003
.venv/bin/python -m forge.forge_cli gen --dim parallel-scheduling --seed 3 --difficulty medium --out tasks
```

- [ ] **Step 2: Audit the regenerated task**

```bash
.venv/bin/python -c "
from pathlib import Path
from forge.maf.leak_audit import audit, image_files
d = sorted(Path('tasks').glob('parallel-scheduling-*'))[0]
print('files in agent image:', [str(p.relative_to(d)) for p in image_files(d)])
print('violations:', audit(d))
"
```

Expected: files are `environment/task.json` only; violations is `[]`.

- [ ] **Step 3: Confirm the seed brute-force now fails**

```bash
.venv/bin/python -c "
from pathlib import Path
d = sorted(Path('tasks').glob('parallel-scheduling-*'))[0]
assert not (d / 'environment' / 'lib').exists(), 'lib still in image'
assert (d / 'tests' / 'lib' / 'maf_dim.py').exists(), 'verifier lost its module'
print('generator absent from image; present for the verifier. Exploit 4 is dead.')
"
```

- [ ] **Step 4: Run the task through Harbor with the oracle**

```bash
harbor run --path tasks/parallel-scheduling-0003 --agent oracle -n 1
```

Expected: reward 1.0. This proves relocating the module did not break in-container grading — the verifier finds `maf_dim.py` at `/tests/lib` because Harbor uploads `tests/` before running `test.sh`.

If this fails with `ModuleNotFoundError: maf_dim`, the `sys.path.insert` in Task 3 Step 4 is wrong; check the upload target with `harbor/models/task/paths.py:104`.

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/python -m pytest forge/tests/ -v`

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add tasks/
git commit -m "chore(tasks): regenerate scheduling task without the leak

environment/ now contains task.json only. Verified: harbor run --agent
oracle scores 1.0, so grading still works with the module at /tests/lib."
```

---

## Self-Review

**Spec coverage.** This plan covers spec §7 (Task 1), §6/G1 (Tasks 2, 3), §6/G2 (Task 4), §6 adversarial tests (Task 5), and §8 build steps 1, 2, 5. Spec §3 (sidecar), §4 (outcome-based reward), §5.1 (belief-tracking), §5.2 (silent-failure-recovery), and §6/G5 (gradient) are explicitly deferred to Plan 2 and named in "Out of scope". Spec §6/G3 (ablation) and G4 (cheater panel) already exist as `V3_ablation` and `V1`/`V2` in `forge/maf/selfcheck.py` and need no work — the spec's claim that G3 needs "promoting to a hard gate" was wrong; `V3_ablation` is already inside `ok=all(checks.values())`. The real hole was the cheater panel's coverage, which Task 4 closes.

**Placeholder scan.** No TBD/TODO. Every code step shows complete code. Task 1 Step 3 item 2 says "delete every sentence claiming X" without quoting each sentence — acceptable because the sentences are located by the failing test from Step 1, which names each claim.

**Type consistency.** `audit(task_dir: Path) -> list[str]` and `image_files(task_dir: Path) -> list[Path]` are defined in Task 2 and used with those signatures in Tasks 3, 5, and 7. `_copy_runtime(dim, lib_dir, include_cli=False)` is defined in Task 3 and its `include_cli` parameter is what Plan 2 will use for the sidecar. `QUARANTINED: dict[str, str]` is defined and consumed in Task 6. `DICTATION_CHEATER: str` is defined on the dimension in Task 4 Step 4, read by `selfcheck` in Step 3, and asserted in Step 1's tests; it names a key of `CHEATERS`, never a policy object.

**Corrections made during review.** Two errors were caught by checking the plan's claims against the code rather than trusting them:

1. The draft's `_dictation` policy for scheduling was byte-for-byte identical to the existing `_serial` (`scheduling.py:121-129`). A gate satisfied by duplicating an existing cheater proves nothing. V4 is now a declaration (`DICTATION_CHEATER = "serial"`) rather than a new policy, which also makes the gate's real demand explicit: the author must answer what obeying their own instruction produces.
2. The draft cited `verify_entry.py:38` for the `sys.path.insert`; it is at line 34.

**Known limitation.** Relocating the module to `tests/` relies on Harbor uploading `tests/` only at verification time. An agent that leaves a background process polling for `/tests` to appear could read it during the verifier phase. This is out of scope: it is exotic relative to the LLM reward-hacking threat model, and Plan 2's sidecar removes the exposure for interactive dimensions by keeping the module in a container the agent has no filesystem path to. It is recorded here rather than left unstated.
