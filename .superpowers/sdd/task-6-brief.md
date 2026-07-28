### Task 6: Quarantine the interactive dimensions

`theory-of-mind` and `failure-recovery` cannot be fixed by relocating the module: their CLI reads the scenario at runtime, inside the agent container, so the scenario must be in the image. Only the sidecar (Plan 2) fixes them. Until then they must not be renderable, or the forge will keep emitting poisoned data.

**Files:**
- Modify: `forge/forge_cli.py:21-34` (`registry`), `:35-72` (`gen`)
- Test: `forge/tests/test_forge_cli.py`

**Interfaces:**
- Consumes: `registry() -> dict[str, Dimension]` (existing).
- Produces: `forge.forge_cli.QUARANTINED: dict[str, str]` — dimension name to reason. Plan 2 removes entries as it ports each dimension.

- [ ] **Step 1: Write the failing test**

Add to `forge/tests/test_forge_cli.py`:

```python
import pytest

from forge.forge_cli import QUARANTINED, main


def test_quarantined_dimension_cannot_be_rendered(tmp_path):
    with pytest.raises(SystemExit) as exc:
        main(["gen", "--dim", "theory-of-mind", "--out", str(tmp_path)])
    assert exc.value.code != 0
    assert not list(tmp_path.iterdir())


def test_quarantine_names_the_reason():
    assert "theory-of-mind" in QUARANTINED
    assert "failure-recovery" in QUARANTINED
    for reason in QUARANTINED.values():
        assert "sidecar" in reason.lower()
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest forge/tests/test_forge_cli.py -v`

Expected: FAIL with `ImportError: cannot import name 'QUARANTINED'`.

- [ ] **Step 3: Implement the quarantine**

In `forge/forge_cli.py`, add after the imports:

```python
# Dimensions whose CLI must read the scenario at runtime inside the agent
# container, so the scenario is necessarily in the agent's image. Relocating the
# module (as static dimensions do) cannot fix them; only the Plan 2 sidecar can.
# Rendering them would emit data whose reward is obtainable by reading the answer.
QUARANTINED = {
    "theory-of-mind": (
        "ground truth ships in the agent image; needs the Plan 2 sidecar. "
        "The construct is also degenerate: the instruction states the optimal "
        "algorithm (asks == q_opt on 12/12 sweep runs)."
    ),
    "failure-recovery": (
        "ground truth ships in the agent image; needs the Plan 2 sidecar."
    ),
}
```

In `gen`, immediately after resolving `reg = registry()`:

```python
    if args.dim in QUARANTINED:
        raise SystemExit(
            f"refusing to render quarantined dimension {args.dim!r}: "
            f"{QUARANTINED[args.dim]}"
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest forge/tests/test_forge_cli.py -v`

Expected: PASS.

- [ ] **Step 5: Remove the poisoned rendered tasks**

The two rendered interactive tasks in `tasks/` still contain readable ground truth. Delete them:

```bash
git rm -r tasks/theory-of-mind-0002 tasks/failure-recovery-0001
```

- [ ] **Step 6: Commit**

```bash
git add forge/forge_cli.py forge/tests/test_forge_cli.py
git commit -m "feat: quarantine the interactive dimensions until the sidecar lands

theory-of-mind and failure-recovery leak ground truth into the agent image
and cannot be fixed by relocating the module -- their CLI reads the scenario
at runtime inside the agent container. Rendering them emits data whose reward
is obtainable by reading the answer, so the forge now refuses.

Also removes the two rendered tasks, which contain readable ground truth."
```

---

