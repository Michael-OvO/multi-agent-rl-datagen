### Task 1: Documentation retraction

`docs/DESIGN.md` claims features that do not exist in `forge/`. Each string below was verified absent. This task is pure removal — no code — and it makes the repo honestly describable immediately.

**Files:**
- Modify: `docs/DESIGN.md`
- Modify: `README.md`
- Test: `forge/tests/test_docs_honesty.py`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing importable. Task 2+ do not depend on this task.

- [ ] **Step 1: Write the failing test**

Create `forge/tests/test_docs_honesty.py`:

```python
"""Docs must not claim capabilities the code does not have.

Every pattern here was verified absent from forge/ during the 2026-07-14 audit.
If you implement one of these for real, delete its entry -- do not weaken the test.

Patterns are word-boundary regexes, not substrings: a bare "liar" substring also
matches "familiar" and "peculiar", which would fail this test for prose that
claims nothing.
"""

import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_DESIGN = _ROOT / "docs" / "DESIGN.md"

# (regex, human name, why it is a lie)
UNIMPLEMENTED_CLAIMS = [
    (r"\bz3\b", "z3", "no z3/CSP solver exists in forge/"),
    (r"\brandom[- ]valid\b", "random-valid", "no random-valid baseline exists in forge/"),
    (r"\bliar\b", "liar", "no liar dimension exists in forge/"),
    (r"\breward\.json\b", "reward.json", "the verifier writes reward.txt, not reward.json"),
    (r"\bheld[- ]out\b", "held-out", "no held-out config machinery exists in forge/"),
]


@pytest.mark.parametrize("pattern,name,why", UNIMPLEMENTED_CLAIMS)
def test_design_does_not_claim_unimplemented_feature(pattern, name, why):
    hits = re.findall(pattern, _DESIGN.read_text(), flags=re.IGNORECASE)
    assert not hits, f"DESIGN.md claims {name!r} ({len(hits)} hits) but {why}"


def test_design_is_not_marked_draft():
    assert "draft for review" not in _DESIGN.read_text().lower()


def test_design_code_fences_are_balanced():
    fences = [ln for ln in _DESIGN.read_text().splitlines() if ln.startswith("```")]
    assert len(fences) % 2 == 0, f"unclosed code fence: {len(fences)} fence markers"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest forge/tests/test_docs_honesty.py -v`

Expected: FAIL. Seven failures — five claim parametrizations, the draft marker, and the fence balance check (DESIGN.md has 13 fence markers).

- [ ] **Step 3: Correct DESIGN.md**

Make these edits:

1. Line 3: replace `**Status:** Draft for review` with `**Status:** Current`.
2. Delete every sentence claiming z3/CSP solving, a random-valid baseline, a liar dimension, `reward.json`, held-out configs, or template variation. Do not reword them into softer claims — delete them.
3. Close the unterminated code fence at end of file (append a line containing exactly ```` ``` ````).
4. Rewrite the "single source of truth" invariant. It currently reads that the dimension module is copied into the task so the in-container verifier grades with the same code the selfcheck validated. That is the root cause of the audit's defects 1, 3, and 4. Replace with:

```markdown
**Isolation invariant.** The dimension module (`generate`, `ORACLE`, `verify`,
`CHEATERS`) never enters the agent's image. Static dimensions ship it to
`tests/lib/`, which Harbor uploads only at verification time. Interactive
dimensions keep it in a sidecar. Identical grading between selfcheck and the
in-container verifier is achieved by shipping the *same file to a place the
agent cannot read* -- not by shipping it to the agent.
```

5. Describe the project as a **deterministic orchestrator microbenchmark forge**. Remove any claim to decomposition or higher-order theory of mind.

- [ ] **Step 4: Correct README.md**

Remove the same claims from `README.md`. Additionally, replace the two `harbor run` examples that reference `tasks/theory-of-mind-0002` with `tasks/parallel-scheduling-0003`, because Task 6 quarantines the interactive dimensions.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest forge/tests/test_docs_honesty.py -v`

Expected: PASS (7 passed).

- [ ] **Step 6: Commit**

```bash
git add docs/DESIGN.md README.md forge/tests/test_docs_honesty.py
git commit -m "docs: retract unimplemented claims; replace copy-into-task invariant

The 'single source of truth' invariant (copy the dimension module into the
task) is the root cause of the ground-truth leak: generate() is
seed-deterministic, so shipping it lets the agent regenerate /tests content.
Replaced with an isolation invariant. Added a test that fails if the docs
re-acquire claims the code does not implement."
```

---

