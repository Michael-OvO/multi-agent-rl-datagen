# Final whole-branch review — fix report

Branch: `fix/isolation-and-gates`. Base: `8f587e8`. All findings fixed.

**Suite:** `.venv/bin/python -m pytest` from repo root → `87 passed, 2 xfailed`
(baseline was `70 passed, 2 xfailed`; +17 tests, none weakened, none deleted
except one I wrote myself and rejected — see finding 3).

| Commit | Scope |
|---|---|
| `621e3db` | Findings 1 + 2 — G1 ground-truth detection |
| `0ca51cd` | Finding 4 — V4 declaration |
| `3225259` | Finding 3 — sweep generator |
| `60c136c` | Minor findings — docs |

---

## Finding 1 — G1's ground-truth detection was unfalsifiable

Added 7 tests pinning ground-truth detection (`forge/tests/test_leak_audit.py`):
top-level `_`-key produces a violation naming the key; every key named, not just
the first; the violation names the file; and a no-false-positive counterpart on
nested *public* data.

**Sabotage verification** — `_ground_truth_keys` body replaced with `return []`,
exactly the check that exposed the gap:

| | before this work | after |
|---|---|---|
| suite with `_ground_truth_keys` disabled | `70 passed, 2 xfailed` — byte-identical, **0 red** | **7 failed**, 74 passed, 2 xfailed |

The 7 that go red are precisely the ground-truth tests. Restored file → green.

`test_agent_image_hides_ground_truth_and_grader` (`forge/tests/test_harbor.py`)
no longer delegates its entire claim to `audit()`. It now asserts directly that
the shipped `environment/task.json` contains no `_planted`/`_opt_makespan`, and
— so the assertion can't pass vacuously if `generate()` ever stopped planting —
that `tests/ground_truth.json` *does* contain them. Detector and byte-level
spot-check now fail independently.

## Finding 2 — `_ground_truth_keys` fail-opened against its own doctrine

`forge/maf/leak_audit.py`, ~40 lines, no restructuring; the Dockerfile parser is
untouched, `core.py` is untouched.

- recurses nested dicts **and** lists (`_walk_ground_truth_keys`)
- handles a list at the document root
- covers `.jsonl` (one document per line) via `_json_documents`
- an unparseable `.json`/`.jsonl` is now its own violation, not `except
  Exception: return []`

Each shape has a red-verified test (6 red before the fix, all green after).
`audit()`'s docstring now states its real scope *including what it does not
cover* (ground truth under a public-looking name in a non-JSON format).

The shared blind spot with `core.public()` (top-level-only stripping) is
documented in `_ground_truth_keys`' docstring, with the reason it must **not**
be narrowed to match: the scanner recursing further than the producer strips is
exactly what lets it catch the producer's most likely regression.

## Finding 3 — `scripts/eval_sweep_gen.py`

Imports `QUARANTINED` from `forge.forge_cli` and filters on `dim.NAME` — the
list is never copied, so lifting the quarantine needs no edit here. Output is
built into a staging dir and swapped in only once the run succeeds; a failed run
leaves the existing set and `baselines.json` untouched.

Red-verified against the pre-fix script, reproducing the reported failure
verbatim: `SystemExit: only 0/2 passing seeds for failure-recovery/easy in 60
scans`.

**One test I wrote and then deleted.** My first draft asserted the quarantine
names were absent from the script's source. It *passed against the buggy
script* — the script hardcoded `"theory_of_mind"` while `QUARANTINED`'s keys
read `"theory-of-mind"`. A test that greens on the exact bug it is named after
is the defect this branch exists to remove, so I replaced it with an end-to-end
run of the real generator (~0.1s).

Sweep regenerated: 6 `parallel-scheduling` instances, quarantined ones skipped
and absent. `tasks/parallel-scheduling-0003`'s copied `maf_dim.py` refreshed
(stale after finding 4); the task is otherwise byte-identical to a fresh
seed-3/medium generation, and `dryrun_local.py` still scores the oracle 1.0.

## Finding 4 — V4's declaration: I agree it is backwards

Declared `DICTATION_CHEATER = "greedy_earliest"`. Reasoning, from reading the
three artifacts rather than the finding:

`OUTPUT_CONTRACT` is not procedure-free. It lists four constraints and then
closes: *"Your score is `optimal_makespan / your_makespan` — so parallelize
independent work across the team."* That final clause is a procedure. `_serial`
is documented *"never parallelize"* — it is the single policy in the panel that
**disobeys** the instruction's only procedural sentence, so it cannot be what
mechanically executing that text produces. `_greedy_earliest` (list-schedule,
lowest-id ready task, capable worker free earliest, no lookahead) is.

Measured, 3 difficulties × 4 seeds — `greedy_earliest` ≥ `serial` in **12/12**
cells:

| cell | serial | greedy_earliest |
|---|---|---|
| easy/0–3 | 0.500 | 0.500 |
| medium/0–3 | 0.375–0.417 | 0.500 |
| hard/0–3 | 0.389–0.400 | 0.500 |

So the old declaration named both the wrong policy *and* the weaker one. No gate
verdict changes (V1 needs all cheaters < 0.6; both ≤ 0.5) — the fix is purely
about the declaration being true, which is V4's entire value.

Red-verified: `test_dictation_cheater_is_the_strongest_cheater_not_the_weakest`
fails on the old declaration (`medium/0: serial 0.393 < greedy 0.5`). It pins
the *property* V4 defines (the declared cheater must not be beaten by another),
not the string `"greedy_earliest"`. A companion test pins the contract sentence
the declaration is derived from, so the premise cannot silently rot again.

## Minor findings

- **`harbor.py:88-89`** — rewrote. `/opt/maf` is outside the agent's *workdir*,
  not its *filesystem*; `cat /opt/maf/scenario.json` is exploit 1. Nothing
  enforced "the agent uses only the CLI" — an assumption about agent behaviour
  stated as a defense. Now says plainly that it is broken and quarantined
  pending the Plan 2 sidecar, and why relocating the file within the image
  cannot fix it.
- **`harbor.py:85`** — "completed in Task 6" → quarantined by Task 6.
- **`DESIGN.md`** §5 diagram (now shows the real `environment/` — Dockerfile +
  public-only `task.json`, plus `tests/ground_truth.json`); deleted the false
  "never exposed through the agent's protocol"; "Interactive dimensions keep it
  in a sidecar" was present tense for unbuilt work → replaced with an explicit
  quarantine paragraph. §9's map rewritten: `forge/common/` and
  `forge/generators/` do not exist; selfcheck is in-process, not in-container;
  `generate()` returns a dict, `write_task` emits the dir. All verified against
  the tree.
- **`leak_audit.py:17-19`, `:167-172`** — corrected, parser unchanged. An
  unrecognized flag is **skipped**, not failed closed; only `--from=` is
  unresolvable. Verified: `COPY --exclude=maf_dim.py lib /app/lib` →
  `unparsed_copies() == []` and the excluded file *is* scanned. The docstring
  now says so, and says why the direction is safe (flags narrow or relocate
  what Docker copies, so ignoring them means scanning a superset — over-report,
  never a silent miss).
- **`README.md:45,56`** — **dropped the count** rather than update it. Argument:
  it rotted twice in one branch (41 → 72 → 89), nothing pins it, and no reader
  chooses this repo for its test count. The stable, informative property is
  "in-process, no Docker" — which is what it now says. Quoting a number no test
  enforces is the same defect class in prose.

---

## Concerns

1. **`scripts/eval_sweep_gen.py` can't be run the way `docs/RESEARCH.md` says.**
   `python scripts/eval_sweep_gen.py` → `ModuleNotFoundError: No module named
   'forge'` (the package isn't installed; `pytest` supplies `pythonpath=["."]`).
   Works as `python -m scripts.eval_sweep_gen` from root. **Pre-existing, not a
   regression** — the old script imported `forge.maf.harbor` identically. Left
   alone as out of scope; a `sys.path` shim vs. packaging is a maintainer call.
2. **`sweep/baselines.json` is a destructiveness trap of the same class as
   finding 3, one level up.** Tracked, 18 entries spanning all three dimensions;
   `sweep/results.json` (also tracked) has 18 matching per-task entries, and
   `docs/RESEARCH.md` publishes that 18-instance sweep. Running the generator
   now legitimately rewrites it with **6** entries — orphaning the 12 the
   aggregator joins against and contradicting the published table. I ran it,
   noticed, and **restored the file** (it is byte-identical to HEAD); the 6
   regenerated instance dirs are gitignored. Nobody asked me to change
   `baselines.json` and destroying historical evidence would be self-defeating
   here — but the hazard is live: the next person to run the script will
   silently truncate it. Needs a decision (merge into the historical record, or
   split "current baselines" from "published sweep evidence").
3. **`_write_interactive` is dead-and-broken, not just broken.** Its Dockerfile
   does `COPY lib /app/lib`, but `_copy_runtime` now writes to `tests/lib`, so
   `environment/lib` never exists and the build would fail outright. Harmless
   (quarantined, unreachable via `forge gen`) and I documented it as unshippable
   rather than repairing a function Plan 2 will replace.
4. **G1 detects ground truth by the `_` naming convention only.** Ground truth
   under a public-looking key, or in a non-JSON format, is out of scope. Now
   stated in `audit()`'s docstring instead of being implied away — but it is a
   real ceiling on what "audit clean" means.
