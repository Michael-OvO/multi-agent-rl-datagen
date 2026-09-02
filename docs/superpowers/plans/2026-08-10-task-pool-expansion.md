# Task-Pool Expansion (Parts A + B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rescue the 4 roster-blind Gaia2 scenarios by roster completion, open the campaign to the four never-fetched Gaia2 splits, and draft the three ability charters — widening the study's informative pool from 3 scripted scenarios to 5+ without spending a model token.

**Architecture:** Part A1 teaches `derive_roster()` (forge/gaia2/mine.py) to complete itself using the same containment evidence that today excludes blind scenarios; the exclusion gates stay as defense-in-depth. Part A2 lets `scenario_paths()` (scripts/gaia2_campaign.py) discover scenarios from every fetched split directory instead of two hard-coded evidence files, then fetches and measures the four missing splits. Part B is three prose charter drafts under `genjobs/`, inert until Michael queues them.

**Tech Stack:** Python 3.11, pytest, the repo's own mine/campaign/probe modules. No new dependencies. Spec: `docs/superpowers/specs/2026-08-10-task-pool-expansion-design.md`.

## Global Constraints

- TDD throughout: every behavior change gets a failing test first, watched failing (`superpowers:test-driven-development`).
- `forge/gaia2/mine.py` ships verbatim into rendered tasks (`harbor.VERBATIM_COPIES`): after any edit to it, refresh `tasks/*/environment/maf_gaia2/mine.py` or the byte-identity drift guard fails. Refresh command is given in Task 1 Step 9.
- The 33 currently-clean scenarios' rosters must remain byte-identical (spec Part A1). Pinned by test in Task 1.
- No paid episodes anywhere in this plan. Fetching parquet files (Task 4) is network but not model spend.
- Suite must be green (`.venv/bin/python -m pytest -q`) and `ruff check forge scripts` clean at every commit.
- Run everything with the main venv: `.venv/bin/python`. Never `.venv-gaia2` (that env is for `are.simulation` episodes only).
- The next paid campaign after this plan carries a new label (`v6`); this plan does not run it.

---

### Task 1: Roster completion in the miner (spec A1)

**Files:**
- Modify: `forge/gaia2/mine.py` (functions `derive_roster`, `roster_blind_facts`, dataclass `Gaia2Span`, function `admit`)
- Test: `forge/tests/test_gaia2_mine.py`

**Interfaces:**
- Consumes: existing `_string_leaves`, `app_state_values`, `_given_text`, `gold_writes`, `information_seams`, `BlindFact`, `CONTAINMENT_MIN_LEN`, `MIN_VALUE_LEN`, `MAX_SEAM_SOURCES` — all already in `forge/gaia2/mine.py`.
- Produces: `derive_roster(scenario) -> tuple[str, ...]` now returns the *completed* roster. New field `Gaia2Span.roster_completed: tuple[str, ...]` (the apps completion added, `()` when none). `roster_blind_facts(scenario)` unchanged signature, now computed against the completed roster (empty whenever completion succeeded). New private helper `_blind_facts_for(scenario, roster) -> tuple[BlindFact, ...]` (the roster-parameterized core, used by both).

**Background for the implementer:** today `roster_blind_facts()` calls `derive_roster()` and reports facts only reachable outside that roster; admission then *excludes* the scenario. The change inverts the ending: `derive_roster()` itself runs the blind-fact scan against its provisional roster and unions in the source apps. The scan and the roster would now be mutually recursive — that is why the core moves into `_blind_facts_for(scenario, roster)` which takes the roster as a parameter instead of computing it.

- [ ] **Step 1: Write the failing tests**

Append to `forge/tests/test_gaia2_mine.py`:

```python
# -- roster completion: the blind evidence names the repair ------------------
#
# roster_blind_facts proves a fact lives only in off-roster apps -- and its
# `sources` name exactly the apps the roster is missing. Instead of excluding
# the scenario, derive_roster now adds them. The exclusion gates downstream
# stay as defense-in-depth, but for every scenario whose blind facts carry
# providers (which is all of them, by the detector's construction), the
# scenario becomes solvable instead of dead.


def test_completion_adds_the_blind_facts_source_apps():
    span = admit(_load("blind"))
    assert span.roster == ("Contacts", "Emails", "Files")
    assert span.roster_completed == ("Files",)
    assert span.roster_blind == ()
    assert span.partition_complete


def test_clean_scenarios_are_not_touched_by_completion():
    # The 33 clean scenarios must remain byte-identical (spec A1). The two
    # clean fixtures pin the exact rosters.
    seamful = admit(_load("seamful"))
    assert seamful.roster == ("Contacts", "Emails")
    assert seamful.roster_completed == ()
    operation = admit(_load("operation"))
    assert operation.roster == ("Calendar", "Shopping")
    assert operation.roster_completed == ()


def test_completion_reaches_a_fixed_point_in_one_pass():
    # After the sources join the roster, a re-scan against the completed
    # roster finds nothing: every provider is now a seat.
    from forge.gaia2.mine import _blind_facts_for, derive_roster

    scenario = _load("blind")
    assert _blind_facts_for(scenario, derive_roster(scenario)) == ()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest forge/tests/test_gaia2_mine.py -q -k "completion or not_touched"`
Expected: FAIL — `roster_completed` is not a field, and the blind fixture's roster lacks `Files`. (`test_a_fact_only_readable_outside_the_roster_marks_the_scenario_blind` will also start failing; Step 3 note handles it.)

- [ ] **Step 3: Implement**

In `forge/gaia2/mine.py`:

3a. Rename the body of `roster_blind_facts` into the parameterized core, and make the public function delegate. The existing body already computes `roster = set(derive_roster(scenario))` — that line is replaced by the parameter:

```python
def _blind_facts_for(scenario: dict,
                     roster: tuple[str, ...]) -> tuple[BlindFact, ...]:
    """The blind-fact scan against an explicit roster.

    Split out of roster_blind_facts because derive_roster needs to run the
    scan against its own provisional roster -- with the public function
    calling derive_roster, the pair would recurse.
    """
    # ... the entire existing body of roster_blind_facts, with
    #     `roster = set(derive_roster(scenario))` replaced by
    #     `roster = set(roster)` ...


def roster_blind_facts(scenario: dict) -> tuple[BlindFact, ...]:
    """Facts consumed by gold writes that only off-roster apps can supply.

    Computed against the *completed* roster (see derive_roster): whenever a
    blind fact carries providers, completion has already seated them, so a
    non-empty result now means completion could not repair the scenario --
    kept as defense-in-depth for the gates downstream.
    """
    return _blind_facts_for(scenario, derive_roster(scenario))
```

3b. Completion in `derive_roster`:

```python
def derive_roster(scenario: dict) -> tuple[str, ...]:
    """Apps the gold writes touch, plus apps a seam proves were read, plus
    apps that hold a fact the gold writes consume that nothing else supplies.

    The third clause is completion: the blind-fact scan's `sources` name the
    apps the base roster is missing (a Files app holding the attachment the
    gold emails send; the Contacts app holding the deciding job title).
    Before completion existed those scenarios were excluded as unsolvable --
    four of the 37, at full episode price before anything noticed.
    """
    apps = {write.app for write in gold_writes(scenario)}
    apps |= {seam.source for seam in information_seams(scenario)}
    base = tuple(sorted(apps))
    apps |= {app for fact in _blind_facts_for(scenario, base)
             for app in fact.sources}
    return tuple(sorted(apps))
```

3c. `Gaia2Span` gains the field (after `roster_blind`):

```python
    #: Apps that joined the roster by completion rather than by write or
    #: seam evidence -- () for the untouched majority. Recorded so every
    #: completion is auditable in the admission evidence.
    roster_completed: tuple[str, ...] = ()
```

3d. `admit()` computes it (replace the existing constructor call):

```python
def admit(scenario: dict) -> Gaia2Span:
    """Measure one scenario. `usable` and `seamful` are read off the result."""
    seams = tuple(information_seams(scenario))
    roster = derive_roster(scenario)
    base = {write.app for write in gold_writes(scenario)}
    base |= {seam.source for seam in seams}
    return Gaia2Span(
        scenario_id=scenario_id(scenario),
        roster=roster,
        write_apps=tuple(sorted({w.app for w in gold_writes(scenario)})),
        seams=seams,
        conditioned_env_events=conditioned_env_events(scenario),
        delegation_target=delegation_target(scenario),
        roster_blind=roster_blind_facts(scenario),
        roster_completed=tuple(sorted(set(roster) - base)),
    )
```

3e. **Rework the three tests that treated the blind fixture as excluded** (they now describe the old behavior):

- In `forge/tests/test_gaia2_mine.py`, delete `test_a_fact_only_readable_outside_the_roster_marks_the_scenario_blind` (superseded by `test_completion_adds_the_blind_facts_source_apps`). Keep `test_a_roster_covered_scenario_is_not_blind`, `test_instruction_supplied_facts_are_never_blind`, `test_short_fragments_do_not_mark_blindness`, and `test_a_fact_delivered_by_an_environment_event_is_not_blind` — they still pass and still pin the detector's boundary (short fragments: the Files app's leaves are below the containment guard, so no blind facts and *no completion* — assert `roster_completed == ()` there too).
- In `forge/tests/test_gaia2_render.py`, replace `test_blind_scenarios_render_nothing` with:

```python
def test_a_completed_scenario_renders_with_its_added_specialist():
    # The blind fixture used to render nothing; completion seats the Files
    # app, so it renders the full grid and every cell's roster carries it.
    cells = render_cells([_load("blind")])
    assert len(cells) == 4
    assert all("Files" in c.roster for c in cells)
```

(Check `CellSpec` for the roster attribute name before writing the assert — `grep -n "class CellSpec" -A 12 forge/gaia2/render.py`.)

- In `forge/tests/test_gaia2_campaign.py`, `test_direct_cell_run_refuses_a_blind_scenario_before_spending` uses the blind fixture, which now admits. Convert it to a monkeypatched fake so the gate (kept per spec) stays tested:

```python
def test_direct_cell_run_refuses_a_blind_scenario_before_spending(monkeypatch):
    # Completion makes real blind scenarios rare-to-impossible, but the gate
    # stays: it is the last line before money. Fake a span that completion
    # could not repair.
    import pytest

    import scripts.gaia2_cell_run as cell_run
    from forge.gaia2.mine import BlindFact

    blind_span = type("S", (), {
        "scenario_id": "fake", "roster": ("Emails",), "usable": True,
        "roster_blind": (BlindFact(app="Emails", function="send_email",
                                   arg="attachment_paths",
                                   leaf="wikipedia_41.txt",
                                   sources=("Files",)),),
    })()
    monkeypatch.setattr(cell_run, "admit", lambda scenario: blind_span)
    with pytest.raises(SystemExit, match="roster-blind"):
        cell_run.main(["--scenario", "forge/tests/fixtures/gaia2/blind.json",
                       "--ability", "control"])
```

`test_a_roster_blind_scenario_never_runs` (eligible) already uses a
SimpleNamespace fake — it keeps working; only confirm the fake `span()`
helper gains nothing (it does not need `roster_completed`).

- [ ] **Step 4: Run the full mine/render/campaign tests**

Run: `.venv/bin/python -m pytest forge/tests/test_gaia2_mine.py forge/tests/test_gaia2_render.py forge/tests/test_gaia2_campaign.py -q`
Expected: PASS.

- [ ] **Step 5: Real-data integration check (only runs when gaia2_data is fetched locally)**

Append to `forge/tests/test_gaia2_mine.py`:

```python
def test_completion_on_the_recorded_blind_scenarios():
    import pytest
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    s24 = root / "gaia2_data" / "mini" / "scenario_universe_24_tg3h3h.json"
    if not s24.exists():
        pytest.skip("gaia2_data is not fetched (gitignored)")
    span = admit(json.loads(s24.read_text()))
    assert "Files" in span.roster and span.roster_completed == ("Files",)
    assert span.roster_blind == ()

    clean = root / "gaia2_data" / "mini" / "scenario_universe_30_68r6vs.json"
    span = admit(json.loads(clean.read_text()))
    assert span.roster_completed == ()
    assert span.roster == ("Cabs", "Calendar", "Contacts", "Messages")
```

Before committing this test, verify the clean scenario's roster tuple by running it — if the assert on the exact tuple fails, print the actual value, confirm it matches the roster recorded in `sweep/gaia2_mini_admission.json` for that scenario (it must — that is the byte-identity requirement), and fix the literal in the test.

- [ ] **Step 6: Run**

Run: `.venv/bin/python -m pytest forge/tests/test_gaia2_mine.py -q`
Expected: PASS (or SKIP for the integration test on machines without data).

- [ ] **Step 7: Full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: 3 failures in `test_gaia2_harbor.py::test_committed_tasks_match_the_generator[environment/maf_gaia2/mine.py-...]` — the drift guard noticing `mine.py` changed. Everything else green. If `test_docs_honesty` fails, read its message: it means prose somewhere states the old exclusion behavior; fix the named prose to describe completion (likely candidates: none expected — the README never documented blindness counts).

- [ ] **Step 8: Refresh the shipped copies**

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
from forge.gaia2.harbor import VERBATIM_COPIES
dest = "environment/maf_gaia2/mine.py"
for task in sorted(Path("tasks").glob("gaia2-*")):
    (task / dest).write_text(VERBATIM_COPIES[dest].read_text())
    print(f"{task.name}: refreshed")
PY
```

- [ ] **Step 9: Full suite + ruff, both green**

Run: `.venv/bin/python -m pytest -q && .venv/bin/python -m ruff check forge scripts`
Expected: all pass.

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "Complete blind rosters instead of excluding them

roster_blind_facts proves a fact lives only in off-roster apps -- and its
sources name exactly the apps the roster is missing. derive_roster now
seats them (recorded in Gaia2Span.roster_completed, audited in the
admission evidence); the exclusion gates stay as defense-in-depth. The
four excluded scenarios rejoin the pool: s24 gains Files, s22 gains
Contacts/InternalContacts, the two soft ones gain Messages/Chats. The
scripted population goes 3 -> 5. Clean scenarios' rosters are pinned
byte-identical by test."
```

---

### Task 2: Admission evidence records completion; dry-run shows the widened grid

**Files:**
- Modify: `scripts/gaia2_admission_probe.py` (the row dict and the console summary)
- Modify: `scripts/gaia2_campaign.py` (only the `eligible()` docstring and the `--scripted-only` help text if their counts read stale — check in Step 4)
- Evidence: `sweep/gaia2_mini_admission.json`, `sweep/gaia2_adaptability_admission.json` (regenerated)

**Interfaces:**
- Consumes: `Gaia2Span.roster_completed` from Task 1.
- Produces: admission JSON rows gain `"roster_completed": [...]`; console prints a completed count.

- [ ] **Step 1: Add the field to the probe row**

In `scripts/gaia2_admission_probe.py`, the row dict (it already has `"roster_blind"`); add after `"roster"`:

```python
                "roster_completed": list(span.roster_completed),
```

And in the console summary block (it already prints the roster-blind line):

```python
    completed = sum(1 for r in rows if r["roster_completed"])
    print(f"roster-completed (a missing app was seated): {completed}")
```

- [ ] **Step 2: Regenerate the admission evidence**

```bash
.venv/bin/python -m scripts.gaia2_admission_probe
.venv/bin/python -m scripts.gaia2_admission_probe --split adaptability
```

Expected console: `roster-blind ... : 0` and `roster-completed ... : ` 2 for mini (s24, s22) and 2 for adaptability (5flf8t, 6wkrhc — verify against the table in the spec; 21_y6td7z is mini, 21_5flf8t is adaptability — trust the probe's output over this parenthetical and record what it says).

- [ ] **Step 3: Verify the widened scripted grid**

Run: `.venv/bin/python -m scripts.gaia2_campaign --dry-run --label v6 --scripted-only`
Expected: `20 cells to run` across 5 scenarios (the original 3 plus `scenario_universe_22_bt12gw` and `scenario_universe_24_tg3h3h`), every line `judge=scripted`. If the count differs, stop and diagnose before committing — `eligible()` or completion is wrong.

- [ ] **Step 4: Reconcile stale counts in docstrings**

Check `eligible()`'s docstring and the `--scripted-only` help in `scripts/gaia2_campaign.py`: both say "5 of the 37" — after completion that is still literally true (5 script-judgeable of 37), so likely no edit. The `eligible()` docstring's sentence about "148 of which 128 are structurally pinned" also still describes v3 history accurately. Only edit if a sentence now states something false; do not rewrite history notes.

- [ ] **Step 5: Full suite + ruff**

Run: `.venv/bin/python -m pytest -q && .venv/bin/python -m ruff check forge scripts`
Expected: green.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "Record roster completion in the admission evidence

Every completion is auditable: the probe rows carry roster_completed, the
console counts them, and the regenerated evidence shows the rescued four.
The scripted dry-run now prices 20 cells across 5 scenarios."
```

---

### Task 3: Campaign discovers scenarios from every fetched split

**Files:**
- Modify: `scripts/gaia2_campaign.py` (`scenario_paths`)
- Test: `forge/tests/test_gaia2_campaign.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `scenario_paths(root: Path = ROOT) -> dict[str, Path]` — same return shape, new optional `root` parameter for tests, discovery by directory glob instead of the two evidence files.

**Background:** today `scenario_paths()` reads two hard-coded evidence files (`sweep/gaia2_cells.json`, `sweep/gaia2_cells_adaptability.json`) as the scenario list. That leaves the four new splits invisible no matter what is fetched. Discovery moves to the split directories themselves; admission still gates every scenario inside `main()`'s loop (`eligible(admit(...))`), so nothing unadmitted can run.

- [ ] **Step 1: Write the failing test**

Append to `forge/tests/test_gaia2_campaign.py`:

```python
def test_scenario_paths_discovers_every_fetched_split(tmp_path):
    # Discovery must not depend on which evidence files exist: a fetched
    # split directory is the source of truth, admission gates each scenario
    # later. Earlier splits win duplicates (mini before the capability
    # splits, which overlap it).
    from scripts.gaia2_campaign import scenario_paths

    data = tmp_path / "gaia2_data"
    (data / "mini").mkdir(parents=True)
    (data / "search").mkdir()
    (data / "mini" / "scenario_a.json").write_text("{}")
    (data / "search" / "scenario_a.json").write_text("{}")   # duplicate
    (data / "search" / "scenario_b.json").write_text("{}")

    found = scenario_paths(root=tmp_path)
    assert set(found) == {"scenario_a", "scenario_b"}
    assert found["scenario_a"].parent.name == "mini", "mini must win the dup"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest forge/tests/test_gaia2_campaign.py -q -k discovers`
Expected: FAIL — `scenario_paths() takes 0 positional arguments` (or reads the evidence files and returns nothing for tmp_path).

- [ ] **Step 3: Implement**

Replace `scenario_paths` in `scripts/gaia2_campaign.py`:

```python
#: Split directories in priority order for duplicate scenario ids; mirrors
#: scripts/gaia2_fetch.py SPLITS (not imported -- that module needs pandas).
_SPLITS = ("mini", "adaptability", "ambiguity", "execution", "search", "time")


def scenario_paths(root: Path = ROOT) -> dict[str, Path]:
    """Every fetched scenario file, deduplicated by id, earlier splits first.

    Discovery is by directory: a fetched split is visible immediately, and
    admission gates each scenario in the run loop (`eligible(admit(...))`),
    so nothing unadmitted can run. mini comes first because the capability
    splits overlap it and the mini copy is the one the committed evidence
    describes.
    """
    seen: dict[str, Path] = {}
    for split in _SPLITS:
        for path in sorted((root / "gaia2_data" / split).glob("scenario_*.json")):
            seen.setdefault(path.stem, path)
    return seen
```

- [ ] **Step 4: Run the test; then confirm the live pool is unchanged**

Run: `.venv/bin/python -m pytest forge/tests/test_gaia2_campaign.py -q`
Expected: PASS.

Run: `.venv/bin/python -m scripts.gaia2_campaign --dry-run --label v6 --scripted-only`
Expected: still `20 cells` — only mini and adaptability are fetched, and the glob finds the same scenarios the evidence files listed. If the count changed, the glob picked up something admission rejects differently — diagnose before committing.

- [ ] **Step 5: Full suite + ruff, commit**

```bash
.venv/bin/python -m pytest -q && .venv/bin/python -m ruff check forge scripts
git add -A
git commit -m "Discover campaign scenarios from the split directories

scenario_paths globbed two hard-coded evidence files; the four unfetched
splits would have been invisible forever. Discovery moves to the fetched
directories (mini first, so the capability splits' overlap resolves to the
copies the committed evidence describes); admission still gates every
scenario in the run loop."
```

---

### Task 4: Fetch and measure the four missing splits (spec A2)

**Files:**
- Evidence: `sweep/gaia2_ambiguity_admission.json`, `sweep/gaia2_execution_admission.json`, `sweep/gaia2_search_admission.json`, `sweep/gaia2_time_admission.json` (new, committed)
- No source changes. Network downloads; ~160MB parquet per split; `gaia2_data/` is gitignored.

- [ ] **Step 1: Fetch (one command per split; each is resumable and skips if present)**

```bash
for s in ambiguity execution search time; do
  .venv/bin/uv run --with pandas --with pyarrow python -m scripts.gaia2_fetch --split $s
done
```

(If `.venv/bin/uv` does not exist, use plain `uv run --with pandas --with pyarrow python -m scripts.gaia2_fetch --split $s` from the repo root — that is the README's own idiom.)

- [ ] **Step 2: Measure**

```bash
for s in ambiguity execution search time; do
  .venv/bin/python -m scripts.gaia2_admission_probe --split $s
done
```

Record each console summary (scenarios / usable / seamful / roster-blind / roster-completed).

- [ ] **Step 3: Count the widened pool**

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path
from scripts.gaia2_campaign import scenario_paths, eligible
from forge.gaia2.mine import admit

pool = scenario_paths()
scripted = soft = 0
for sid, path in pool.items():
    span = admit(json.loads(path.read_text()))
    if not eligible(span, scripted_only=False):
        continue
    if span.reply_conditioned:
        soft += 1
    else:
        scripted += 1
print(f"unique fetched scenarios: {len(pool)}")
print(f"admitted: {scripted + soft}  scripted-judgeable: {scripted}  soft: {soft}")
PY
```

- [ ] **Step 4: Verify the dry run prices the new pool**

Run: `.venv/bin/python -m scripts.gaia2_campaign --dry-run --label v6 --scripted-only`
Expected: `4 × (scripted count from Step 3)` cells, every line `judge=scripted`. **Do not run a paid seed** — the seed is its own go/no-go with Michael (Global Constraints).

- [ ] **Step 5: Commit the evidence with the counts in the message**

```bash
git add sweep/gaia2_*_admission.json
git commit -m "Measure the four never-fetched Gaia2 splits

<paste the per-split summary lines and the Step 3 pool count here --
the numbers are the deliverable. State explicitly how many new
scripted-judgeable scenarios the widened pool adds over the previous 5.>"
```

---

### Task 5: Three charter drafts (spec B)

**Files:**
- Create: `genjobs/2026-08-10-discovery-hidden-knower/charter.md`
- Create: `genjobs/2026-08-10-context-briefing-load/charter.md`
- Create: `genjobs/2026-08-10-economy-metered-calls/charter.md`

**Interfaces:** none — prose, inert until queued. `forge.factory queue` (future M1) must refuse `status: draft`; that refusal is TDD'd in M1's plan, not here.

- [ ] **Step 1: Write the discovery charter**

`genjobs/2026-08-10-discovery-hidden-knower/charter.md`:

```markdown
---
status: draft
owner: michael
ability: capability-discovery
---

# Charter: the hidden knower

**Capability claim.** A coordinator can identify *which* teammate is able to
know a required fact, when no roster listing, tool name, or task text
reveals it — only reasoning about what each role's data could contain.

**Falsifiable counterfactual.** With every specialist's documentation
visible to the coordinator (the study's open control), the task is solved
at high rate by the same models; the gap between that and the
names-only arm is the measured ability. If the open control also fails,
the task is measuring difficulty, not discovery — rebuild it.

**Task shape (for the stage-2 author; not binding).** N specialists with
deliberately uninformative names. Exactly one holds the fact class the
task needs (e.g., which vendor's contract has the renewal clause). Asking
the wrong specialist returns an honest "my data has nothing like that",
consuming a delegation but nothing else. Success = the required write, no
deadline. Difficulty scales by N and by how obliquely the right role's
purpose must be inferred.

**Non-goals.** No timing pressure of any kind (the v4/v5 finding: the
delegation time tax dominates timed tasks and would contaminate the
measurement). No information-poor briefs — the brief content is allowed
to be trivial once the right specialist is found.

**Alternatives considered.** Hiding docs on the existing Gaia2 scenarios
(the current discovery arm) does not work: v4/v5 measured 6/6 passes —
app names alone (Cabs, Calendar) reveal the knower. The knower must be
hidden by construction, which inherited scenarios cannot retrofit.

**Budget override.** none (repo default).
```

- [ ] **Step 2: Write the context charter**

`genjobs/2026-08-10-context-briefing-load/charter.md`:

```markdown
---
status: draft
owner: michael
ability: context-transfer
---

# Charter: the briefing load

**Capability claim.** A coordinator can compose a delegation brief that
carries *all* the facts the executing role needs — when those facts are
many, scattered across the coordinator's own context, and individually
easy to omit.

**Falsifiable counterfactual.** A single agent holding the full context
solves the task trivially (it needs no brief). If the reference
multi-agent team with a complete scripted brief also fails, the task is
hard for other reasons — rebuild it. The measured ability is the gap
between complete-brief performance and the model-authored-brief arm.

**Task shape (for the stage-2 author; not binding).** The coordinator
accumulates K facts (K ≥ 6) across earlier steps — identifiers, amounts,
constraints — and must then delegate one final composite action to a
specialist that sees none of that history. The verifier checks the final
write's arguments against all K facts; each omitted fact fails exactly
one named requirement, so partial credit localizes *which* fact the brief
dropped.

**Non-goals.** No discovery difficulty: the roster is two roles and the
target specialist is obvious. No timing pressure.

**Alternatives considered.** The existing context-transfer arm (docs
visible, information split) never failed on brief content in two seeds —
inherited Gaia2 tasks need too few facts per delegation for briefs to
break. K must be forced up by construction.

**Budget override.** none (repo default).
```

- [ ] **Step 3: Write the economy charter**

`genjobs/2026-08-10-economy-metered-calls/charter.md`:

```markdown
---
status: draft
owner: michael
ability: delegation-economy
---

# Charter: metered calls

**Capability claim.** A coordinator can decide *when a delegation is worth
its price* — planning which questions to bundle, which to skip, and when
its own knowledge suffices — under a hard meter where each delegation
consumes a scarce unit.

**Falsifiable counterfactual.** With the meter removed, the same models
solve the task at high rate by delegating freely; the measured ability is
the yield gap between unmetered and metered runs at a meter set to the
reference solution's delegation count + 1. If the reference solution
itself cannot fit the meter, the meter is wrong — rebuild it.

**Task shape (for the stage-2 author; not binding).** The meter is a
resource *in the world* (e.g., each delegation consumes one courier
credit; the account holds M), not wall-clock — the v4/v5 finding is that
time-based pressure measures the delegation time tax, which contaminates
the ability. Exceeding the meter is a hard failure by the world's own
rules, not a soft penalty: the study's soft-bN economy arm never
distinguished itself from context-transfer in two seeds.

**Non-goals.** No timing pressure. No hidden information — every fact is
reachable, the question is only what each delegation costs.

**Alternatives considered.** Keeping the soft budget (bN as an auxiliary
reward) — measured twice, indistinguishable from the context arm at these
sample sizes. A hard meter makes over-delegation legible as its own
failure mode.

**Budget override.** none (repo default).
```

- [ ] **Step 4: Commit**

```bash
git add genjobs/
git commit -m "Draft the three ability charters, inert until queued

One per ability, each shaped so its ability decides pass/fail and the
measured confounds (the delegation time tax above all) cannot. status:
draft in front-matter; forge.factory queue (M1) will refuse drafts, and
Michael's edit-and-queue is the approval act -- the amendment to the
orchestrator design's decision 4 recorded in the 2026-08-10 spec."
```

---

### Task 6: Plan checkpoint — suite, evidence coherence, report

**Files:** none created; this is the close-out gate.

- [ ] **Step 1: Full verification**

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check forge scripts
git status --short   # must be clean
```

- [ ] **Step 2: Verify the study-facing numbers one more time**

```bash
.venv/bin/python -m scripts.gaia2_campaign --dry-run --label v6 --scripted-only | head -3
```

Record the cell count; it is the headline of the report to Michael.

- [ ] **Step 3: Report**

Report to Michael: the new scripted pool size, the per-split admission
yields, the three charter paths awaiting his edit, and the explicit
go/no-go he owns: the v6 seed (paid) on the widened pool, and the M1
factory plan as the next writing-plans session.

---

## Self-review (done at write time)

- **Spec coverage:** A1 → Tasks 1–2. A2 → Tasks 3–4. B → Task 5. Part C deferred to its own plans per the spec's sequencing — not a gap. The spec's "campaign dry-run must show 20 scripted cells" → Task 2 Step 3. Evidence fields → Task 2. Comparability/new-label rule → Global Constraints.
- **Placeholders:** Task 4 Step 5's commit message contains a deliberate paste-the-numbers instruction — the numbers cannot be known before the fetch runs; the instruction says exactly what to paste. No other TBDs.
- **Type consistency:** `roster_completed: tuple[str, ...]` in Task 1 matches `list(span.roster_completed)` in Task 2 and the fake span in Task 1 Step 3e (which needs no `roster_completed` — only `eligible()`'s fields). `scenario_paths(root=...)` signature in Task 3 matches Task 4 Step 3's call with no argument (default `ROOT`).
```
