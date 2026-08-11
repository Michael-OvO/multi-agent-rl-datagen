"""Drive the generation-job factory.

    python -m forge.factory.cli queue genjobs/2026-08-10-hidden-knower
    python -m forge.factory.cli status
    python -m forge.factory.cli board
    python -m forge.factory.cli abandon 2026-08-10-hidden-knower

Every verb takes `--root` so the whole surface is testable against a
temporary directory: no git, no network, no sessions. Branch and worktree
creation are deliberately absent from this milestone -- the state records
where they will be, and the session harness that needs them creates them.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from forge.factory.board import render_board
from forge.factory.machine import abandon as abandon_job
from forge.factory.store import (
    discover,
    now_iso,
    queue_job,
    write_state,
)

DEFAULT_ROOT = Path("genjobs")
DEFAULT_WORKTREE_ROOT = Path(".factory-worktrees")


def _find(root: Path, job: str):
    states = discover(root)
    if not states:
        raise SystemExit(f"no jobs under {root}; queue a charter first")
    for state in states:
        if state.job == job:
            return state
    raise SystemExit(
        f"{job}: no such job under {root}; queued jobs are "
        f"{sorted(s.job for s in states)}")


def cmd_queue(args: argparse.Namespace) -> None:
    state = queue_job(args.root, args.charter_dir, now=now_iso(),
                      worktree_root=args.worktree_root)
    print(f"{state.job}: {state.status} at stage {state.stage}, "
          f"branch {state.branch}")
    print(f"  budget {state.caps.total_tokens:,} tokens, "
          f"{state.caps.attempts_per_stage} attempts per stage")


def cmd_status(args: argparse.Namespace) -> None:
    states = discover(args.root)
    if args.job:
        states = [s for s in states if s.job == args.job] or [
            _find(args.root, args.job)]
    if not states:
        print(f"no jobs under {args.root}")
        return
    for state in states:
        print(f"{state.job:44} {state.status:24} stage {state.stage:>2}/10  "
              f"{state.spend.total_tokens:>12,} tokens  updated {state.updated}")


def cmd_abandon(args: argparse.Namespace) -> None:
    state = _find(args.root, args.job)
    after = abandon_job(state, now=now_iso())
    write_state(args.root / after.job, after)
    print(f"{after.job}: {after.status}")


def cmd_board(args: argparse.Namespace) -> None:
    states = discover(args.root)
    args.root.mkdir(parents=True, exist_ok=True)
    out = args.root / "board.html"
    out.write_text(render_board(states, generated=now_iso(),
                                refresh_seconds=args.refresh))
    print(f"wrote {out} ({len(states)} jobs)")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m forge.factory.cli",
        description=(__doc__ or "").split("\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)

    # `--root` is declared on each subparser, not on the top-level parser:
    # argparse only accepts a parent parser's own options before the
    # subcommand name, and every test here drives the CLI as
    # `["queue", path, "--root", root]` -- the option after the verb.
    p_queue = sub.add_parser("queue", help="register a charter directory")
    p_queue.add_argument("charter_dir", type=Path)
    p_queue.add_argument("--root", type=Path, default=DEFAULT_ROOT,
                         help="the job queue directory (default: genjobs)")
    p_queue.add_argument("--worktree-root", type=Path,
                         default=DEFAULT_WORKTREE_ROOT)
    p_queue.set_defaults(fn=cmd_queue)

    p_status = sub.add_parser("status", help="what every job is doing")
    p_status.add_argument("--job", default=None)
    p_status.add_argument("--root", type=Path, default=DEFAULT_ROOT,
                          help="the job queue directory (default: genjobs)")
    p_status.set_defaults(fn=cmd_status)

    p_abandon = sub.add_parser("abandon", help="stop a job, by human decision")
    p_abandon.add_argument("job")
    p_abandon.add_argument("--root", type=Path, default=DEFAULT_ROOT,
                           help="the job queue directory (default: genjobs)")
    p_abandon.set_defaults(fn=cmd_abandon)

    p_board = sub.add_parser("board", help="render genjobs/board.html")
    p_board.add_argument("--root", type=Path, default=DEFAULT_ROOT,
                         help="the job queue directory (default: genjobs)")
    p_board.add_argument("--refresh", type=int, default=5,
                         help="page self-reload interval in seconds")
    p_board.set_defaults(fn=cmd_board)

    args = parser.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main(sys.argv[1:])
