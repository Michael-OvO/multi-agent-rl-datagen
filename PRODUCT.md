# PRODUCT.md — multi-agent-rl-datagen

## What this is

A research forge that turns single-agent benchmark tasks (Gaia2, on Meta's
Agents Research Environments) into multi-agent reinforcement-learning data: a
Main coordinator delegating to app specialists under measured constraint
knobs, judged by the benchmark's own verifier -- its ground truth, matching,
hard checks and checker prompts unmodified; one defect in how it reads its
own checker's answer is fixed and disclosed (`forge/gaia2/judge_parse.py`). The repo's culture
is evidentiary — one file per claim, every number names the file that produced
it, and the shipped write-up is a LaTeX report.

## Audience

One researcher (the maintainer) and collaborators reviewing runs: people who
live in terminals, read proceedings papers, and distrust dashboards that
assert more than their data shows.

## Surfaces

- `trajectory_viewer.html` — the one visual surface: a single-file,
  no-dependency, offline viewer of episode trajectories, shipped tasks with their campaign episodes and verifier breakdowns, and sweep evidence. Mode: Operate. Its committed
  visual world is the proceedings/booktabs evidence page (see DESIGN.md).
- Everything else is CLI and files.

## Constraints

- The viewer must stay a single self-contained HTML file: no server, no
  build step, no network dependency, working from `file://` in any browser.
- It carries its data as an embedded JSON snapshot refreshed by
  `uv run python -m scripts.embed_logs`; live folder reading layers on top.
- Truthfulness outranks polish: verdicts, counters, and citations come from
  the artifacts verbatim; nothing is summarized beyond what a file states.

## Brand commitments

- No invented claims, metrics, or logos. The repo's own vocabulary (Main,
  specialist, seam, knob, verdict, floor) is the product's language.
