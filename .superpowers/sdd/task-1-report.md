# Task 1 Report: Documentation retraction

## Summary

Created `forge/tests/test_docs_honesty.py` verbatim from the brief (7 tests), confirmed it
failed as expected (7 failed), corrected `docs/DESIGN.md` and `README.md` to remove every
unimplemented claim, confirmed all 7 tests pass, ran the full suite (41 passed), and committed.

No production code was touched — this task was pure documentation + one new test file.

## Step 2: confirmed the test fails first

Before editing DESIGN.md, ran the new test file and got exactly the expected shape of failure:
5 claim parametrizations failed (z3, random-valid, liar, reward.json, held-out), plus the draft
marker and the fence-balance check (13 fence markers, odd). 7 failed, as the brief predicted.

## Deletions from `docs/DESIGN.md` (original text of each deletion)

1. **Status line.** `**Status:** Draft for review` → `**Status:** Current`.

2. **`① Task decomposition`** removed from the capability spine ASCII diagram (§1), the
   `parallel-scheduling` capability-column cell (`(+①,③)` → `(+③)`), the §2.2 failure-mode
   table row (`| ① Decomposition | Over/under-decompose; emit "steps" that aren't
   independently dispatchable; conflate decomposition with ordering. | Subtasks are given as
   a DAG; ... |`), the §2.3 curriculum bullet (`**You cannot schedule (②) what you cannot
   decompose (①).** Scheduling operates on a subtask graph; a wrong graph makes scheduling
   ill-posed.`), and the §6.1 `Trains:` line (`② dependency ID + parallel scheduling; ①
   reading structure; ③ assignment.` → dropped `① reading structure`). Rationale: the
   `parallel-scheduling` generator hands the agent an already-built DAG; the agent never
   performs decomposition, so claiming it as a trained/tested capability was false. This was
   brief item 5 ("remove any claim to decomposition"), which I resolved by deleting every
   place the spine numbered it as capability ①, per the ambiguity-resolution rule (a table
   row/list item that exists only to assert an unimplemented claim gets deleted whole).

3. **z3 / CSP solver** — C3 table cell: `ToM: a CSP solver (z3) asserts **exactly one**
   model; scheduling: ...; recovery: ...` → replaced the z3 clause with the actual mechanism
   I verified in `forge/maf/dimensions/theory_of_mind.py` (`unique_ground_truth()`, a
   suspect-elimination check), since scheduling/recovery clauses in the same row are real and
   the row wasn't claim-only.

4. **random-valid baseline** — V1/V3 table row: `| ② scheduling | serial, greedy-earliest,
   random-valid | ... |` → dropped `random-valid` (verified `CHEATERS = {"serial": ...,
   "greedy_earliest": ...}` in `forge/maf/dimensions/scheduling.py` has no third baseline).

5. **Liar / lying-agent claims** (4 locations), deleted outright, no rewording:
   - §2.2 failure-mode table (ToM row): `; trust a lying agent without cross-check` and
     `; liar variants require cross-checking` clauses.
   - §4.2 shortcut-closure bullet: `Liar variants further require cross-checking.`
   - §6.3 verifier bullet: `Liar variants add a cross-check requirement.`
   - §7 knob table: `lying agents` (Adversarial row) and `/ detect lies` (ToM order row).
   Verified zero `liar`/lying-agent code in `forge/`.

6. **`reward.json`** (3 locations):
   - §4.1: `(and a richer \`reward.json\` with sub-scores for RL credit assignment)`.
   - §5 "Reward shape" paragraph: `` `reward.json` additionally carries sub-scores (`gate`,
     `quality`, `budget_used`, …) for RL credit assignment. ``
   - §9 pipeline diagram comment: `reward.py # shared reward helpers (gate × quality,
     reward.json)` → dropped `, reward.json`. Verifier writes `reward.txt` only
     (`harbor/verifier/verifier.py:73` reference already in the doc confirms this).

7. **Held-out configs** (3 locations):
   - §4.5: whole bullet `**Held-out generator configs** for evaluation (train on seed range A
     / difficulty grid A, eval on B) so we can *measure* overfitting rather than hope it's
     absent.` deleted (list item existed only to claim this).
   - §11 Risks: `; must be *measured* via held-out configs.` trimmed off the "Overfitting to
     generators" bullet, which itself is a genuine, kept risk.
   - §8.2 item 1 mitigation clause `held-out-config eval to *measure* it` removed (see below).

8. **Template variation / paraphrase / cover-story** (6 locations) — confirmed zero
   template/paraphrase/cover-story machinery anywhere in `forge/`:
   - §0 TL;DR: `× surface-template` dropped from the `seed × difficulty × dimension ×
     surface-template` multiplier.
   - §4.5: whole bullet `**Multiple cover-story templates** per dimension (e.g. scheduling as
     a build pipeline, a film production, a kitchen brigade) + a **paraphrase layer** on
     `instruction.md`.` deleted.
   - §4.6: `× template` dropped from `seed × difficulty × template`.
   - §8.1: `× |surface templates|` dropped from the scale-multiplier code block, and the
     bullet `**surface templates** — cover stories × paraphrase.` deleted outright.
   - §8.2 item 1: `*Mitigate:* template diversity + paraphrase + held-out-config eval to
     *measure* it (§4.5).` → rewritten to `*Mitigate:* structural randomization (§4.5).`
     (the risk itself — surface-form homogeneity — is genuine and kept; only the false
     mitigation list was replaced with the one mitigation that's actually in the doc/code:
     structural randomization).

9. **Silent failure** — §6.2 scenario bullet: `; some failures are *silent* and only surface
   as a downstream failure` deleted. Verified in `forge/maf/dimensions/failure_recovery.py`
   that every dispatch failure is reported synchronously in the `dispatch` response
   (`{"result": "FAILURE", ...}`) — nothing surfaces only later/downstream. Also removed
   `silent failures;` from the §7 Adversarial knob row.

10. **Higher-order ToM** — §6.3 `Trains:` line: `⑤ ToM (incl. higher-order); ...` → `⑤ ToM;
    ...` (brief item 5, "remove any claim to ... higher-order theory of mind").

11. **Code fence.** File had 13 `` ``` `` markers (odd → unclosed). Appended one more `` ``` ``
    line at EOF per the brief's exact instruction, bringing the count to 14 (even). Note: the
    trailing fence was a pre-existing dangling opener with no real code content inside it —
    I did not try to "fix" the document structurally, only satisfied the parity the test
    checks, exactly as instructed.

12. **"Describe the project as a deterministic orchestrator microbenchmark forge"** (brief
    item 5) — reworded the opening TL;DR sentence: `We generate RL training tasks that
    target **multi-agent orchestration capabilities** by **inverting the multi-agent
    setup**: ...` → `` `forge` is a **deterministic orchestrator microbenchmark forge**: it
    generates RL training tasks that target **multi-agent orchestration capabilities** by
    **inverting the multi-agent setup**: ... ``.

## The invariant rewrite (brief Step 3 item 4)

Important finding: DESIGN.md, as it stood before my edits, did **not** contain a literal
"single source of truth" paragraph in prose — I grepped the whole file for "single source of
truth", "copied into", "copy into" and got zero hits. The actual "single source of truth"
principle the brief describes lives as a **code docstring**, in
`forge/maf/harbor.py`:

```
Single source of truth: the dimension's Python module is *copied* into the task
(with its one internal import rewritten), so the in-container verifier grades
with exactly the code the selfcheck battery validated.
```

That code is real and currently does exactly what the brief says is the exploit: for static
dimensions, `_copy_runtime()` writes the full dimension module (`generate`, `ORACLE`,
`verify`, `CHEATERS`) to `environment/lib/maf_dim.py`, and `_write_static()`'s Dockerfile does
`COPY lib /app/lib` — i.e. the module ships straight into the agent's own image. Since
`generate()` is seed-deterministic, an agent with shell access to its own image can read
`maf_dim.py`, find the seed embedded in `scenario.json`/`task.json`, and re-derive ground
truth. I did not touch `harbor.py` (that's explicitly out of scope for this doc-only task;
Task 2's leak audit and a later sidecar-redesign task are where the code gets fixed).

Since there was no matching DESIGN.md prose to literally replace, I inserted the brief's exact
replacement markdown as new content in §5 "Task anatomy," immediately after the task-directory
ASCII diagram (the section that describes what ships where), verbatim:

```markdown
**Isolation invariant.** The dimension module (`generate`, `ORACLE`, `verify`,
`CHEATERS`) never enters the agent's image. Static dimensions ship it to
`tests/lib/`, which Harbor uploads only at verification time. Interactive
dimensions keep it in a sidecar. Identical grading between selfcheck and the
in-container verifier is achieved by shipping the *same file to a place the
agent cannot read* -- not by shipping it to the agent.
```

I left the existing "Reward shape" paragraph directly below it (about ground truth never
being exposed through the agent's *protocol*) — it's a complementary, still-true statement
about the CLI/protocol level, not superseded by the new invariant, which is about the
filesystem/image level.

## `README.md` changes

- Replaced both `harbor run --path tasks/theory-of-mind-0002 ...` examples with
  `tasks/parallel-scheduling-0003` (brief Step 4; that task dir exists on disk today, and
  Task 6 quarantines the interactive dimensions).
- Grepped README.md for all 7 flagged strings (z3, random-valid, liar, reward.json, held-out,
  template, silent-failure) plus decomposition/higher-order — zero hits. Nothing else to
  remove there.
- Updated the stale test count (`34` → `41`) in two places (Layout table, Quickstart) since
  adding `test_docs_honesty.py`'s 7 tests to the existing 34-test suite made the old number
  immediately wrong; this felt in-scope of "keep the repo honestly describable" even though
  the brief didn't call it out by name.

## Test results

- Step 2 (pre-fix): `forge/tests/test_docs_honesty.py -v` → **7 failed**, matching the
  brief's predicted failure shape exactly (5 claim params + draft marker + fence balance).
- Step 5 (post-fix): `forge/tests/test_docs_honesty.py -v` → **7 passed**.
- Full suite: `.venv/bin/python -m pytest forge/tests -q` → **41 passed** (34 pre-existing +
  7 new).

## Things I was unsure about / flagged but left alone

- **§9's pipeline diagram is stale relative to the real repo layout.** DESIGN.md's §9 shows
  `forge/common/{harbor_writer.py,reward.py,selfcheck.py}` and
  `forge/generators/{parallel_scheduling,failure_recovery,theory_of_mind}.py`, but the actual
  tree (confirmed via `ls` and README's own Layout table) is `forge/maf/{core.py,
  selfcheck.py, harbor.py}` and `forge/maf/dimensions/{scheduling,failure_recovery,
  theory_of_mind}.py`. This is a real inaccuracy but it's a *structural/naming* drift, not one
  of the 7 audited "claims a feature that doesn't exist" strings, and fixing it felt like
  scope creep beyond "pure removal." I only touched the one line inside that diagram that
  contained `reward.json`. Flagging in case a later task wants to correct the whole diagram.
- **The Isolation-invariant insertion point is my judgment call, not a literal replacement.**
  As described above, no DESIGN.md prose matched the brief's description of what "currently"
  exists — only a code docstring did. I inserted the given text in the most contextually
  fitting spot (§5, right after the task-anatomy directory diagram). If the intended location
  was actually §9 (next to the `harbor_writer.py`/`harbor.py` description) instead, that's an
  easy follow-up move.
- **"Constraint-satisfaction instance" (§6.3 Generation bullet) and "decoy workers" /
  "red-herring clues" (§7) were left as-is** — they describe the actual implementation
  (`theory_of_mind.py`'s elimination-based unique-solution generation; `failure_recovery.py`'s
  literal decoy-worker mechanism) accurately, without invoking z3 or "liar." I did not
  independently verify "red-herring clues" beyond a quick grep (no distractor/red-herring
  code found in `theory_of_mind.py`), but it wasn't in the audited 7-string list, so I left it
  per the brief's explicit scope rather than expanding the audit myself.
- **§4.5's "Mitigations, in increasing strength:" intro line** no longer made sense with only
  one bullet remaining (structural randomization) after deleting the template/held-out
  bullets, so I trimmed it to "Mitigation:" — a small wording tweak beyond the literal brief
  text, done to avoid leaving a "plural mitigations, singular strength-ranking" sentence that
  no longer matched the list under it.

## Commit

```
docs: retract unimplemented claims; replace copy-into-task invariant
```

Files: `docs/DESIGN.md`, `README.md`, `forge/tests/test_docs_honesty.py`.
