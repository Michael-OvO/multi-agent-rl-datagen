"""Watch one episode happen, message by message.

The sweep prints a number per rollout. That is the habit this whole repo is a
warning about: every bug in WRITEUP.md §7 was invisible in the score and sitting
in plain English one level below it. This prints the level below it.

    APPWORLD_ROOT=$PWD python -m scripts.watch_episode
    APPWORLD_ROOT=$PWD python -m scripts.watch_episode --config open
    APPWORLD_ROOT=$PWD python -m scripts.watch_episode --config star-names --task 2a163ab_3

What you are watching:

    MAIN        the model under test (gpt-5.6-sol). Has no APIs. Only delegates.
    -> ask      the brief the Main wrote. This is the thing being measured.
    SPECIALIST  a real LLM (gpt-4.1) bound to one app. Does not know the task.
    code        the Python it wrote
    GATE        forge/appworld/sandbox.py deciding whether that code may run
    world       what AppWorld printed back
    <- report   what the specialist told the Main
    SCORE       AppWorld's own evaluate(). Floor is 0.333, ceiling 1.000.

No Docker. This runs the same `runtime.py` the container runs, against a local
AppWorld, so it is the real thing minus the isolation -- which means it is for
understanding, not for measuring. Numbers come from the sweep.
"""

from __future__ import annotations

import argparse
import os
import textwrap

from forge.appworld.partition import Constraints, Topology, Visibility, control_for

DIM, BOLD, RESET = "\033[2m", "\033[1m", "\033[0m"
BLUE, GREEN, RED, YELLOW = "\033[34m", "\033[32m", "\033[31m", "\033[33m"

CONFIGS = {
    "open": None,  # the control: one agent, every API -- built via control_for()
    "star-docs": (Topology.STAR, Visibility.DOCS),
    "star-names": (Topology.STAR, Visibility.NAMES),
    "chain-names": (Topology.CHAIN, Visibility.NAMES),
}


def _wrap(text: str, indent: str) -> str:
    out = []
    for para in str(text).splitlines():
        out.extend(textwrap.wrap(para, 88, initial_indent=indent,
                                 subsequent_indent=indent) or [indent.rstrip()])
    return "\n".join(out)


def _install_tracing(runtime, sub_model: str) -> None:
    """Print every message the harness passes around."""
    real_chat = runtime.chat
    real_inspect = runtime.inspect_code
    real_feedback = runtime.execution_feedback
    real_run_specialist = runtime.run_specialist

    def chat(client, messages, model=runtime.DEFAULT_MODEL, retries=6):
        out = real_chat(client, messages, model=model, retries=retries)
        who = messages[0]["content"].startswith("You are the Main coordinator")
        if who:
            first = out.strip().splitlines()[0] if out.strip() else ""
            if first.startswith("DELEGATE"):
                target, _, brief = first[len("DELEGATE"):].partition("::")
                print(f"\n{BOLD}{BLUE}MAIN{RESET} -> ask {BOLD}{target.strip()}{RESET}")
                print(_wrap(brief.strip(), "      "))
            elif first.startswith("DONE"):
                print(f"\n{BOLD}{BLUE}MAIN{RESET} -> {BOLD}done{RESET}: "
                      f"{first.partition('::')[2].strip()!r}")
            else:
                print(f"\n{BOLD}{BLUE}MAIN{RESET} {DIM}(malformed, will be corrected){RESET}")
                print(_wrap(first, "      "))
        return out

    def inspect_code(code, app, known=()):
        reason = real_inspect(code, app, known=known)
        label = f"{RED}GATE  REFUSED{RESET}" if reason else f"{GREEN}GATE  ok{RESET}"
        print(f"\n    {DIM}code{RESET}")
        print(_wrap(code, "      "))
        print(f"    {label}" + (f" {DIM}{reason}{RESET}" if reason else ""))
        return reason

    def execution_feedback(result):
        out = real_feedback(result)
        head = out if len(out) < 300 else out[:300] + f" {DIM}...[{len(out)} chars]{RESET}"
        print(f"    {DIM}world{RESET}")
        print(_wrap(head, "      "))
        return out

    def run_specialist(client, world, app, brief, log, model=sub_model, max_turns=14):
        shown = app if isinstance(app, str) else " + ".join(app)
        print(f"\n  {BOLD}{YELLOW}SPECIALIST {shown}{RESET} {DIM}({model}){RESET}")
        report = real_run_specialist(client, world, app, brief, log,
                                     model=model, max_turns=max_turns)
        print(f"\n  {BOLD}{YELLOW}<- report{RESET}")
        print(_wrap(report, "      "))
        return report

    runtime.chat = chat
    runtime.inspect_code = inspect_code
    runtime.execution_feedback = execution_feedback
    runtime.run_specialist = run_specialist


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--task", default="2a163ab_1")
    ap.add_argument("--config", default="star-docs", choices=sorted(CONFIGS))
    ap.add_argument("--main-model", default="gpt-5.6-sol")
    ap.add_argument("--sub-model", default="gpt-4.1")
    args = ap.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY not set (try: set -a && . ./.env && set +a)")

    from appworld import AppWorld
    from openai import OpenAI

    from forge.appworld import runtime
    from forge.appworld.runtime import RunLog, run_main

    _install_tracing(runtime, args.sub_model)

    with AppWorld(task_id=args.task, experiment_name="watch",
                  ground_truth_mode="minimal") as world:
        instruction = world.task.instruction
        roster = tuple(sorted({"phone", "venmo"}))  # this family's roster

        if args.config == "open":
            constraints = control_for(roster)
        else:
            topology, visibility = CONFIGS[args.config]
            constraints = Constraints(roster=roster, topology=topology,
                                      visibility=visibility)

        print(f"{BOLD}task{RESET}   {args.task}")
        print(_wrap(instruction, "       "))
        print(f"{BOLD}config{RESET} {args.config}  {DIM}roster={list(roster)} "
              f"main={args.main_model} specialists={args.sub_model}{RESET}")
        print(f"{DIM}       floor (do nothing) = 0.333    ceiling = 1.000{RESET}")

        log = RunLog()
        if constraints.main_has_apis:
            # The control is one agent holding the whole roster -- no Main at all.
            answer = runtime.run_specialist(OpenAI(), world, roster, instruction,
                                            log, model=args.main_model, max_turns=20)
        else:
            answer = run_main(OpenAI(), world, instruction, constraints, log,
                              model=args.main_model, sub_model=args.sub_model)

        world.execute(
            "apis.supervisor.complete_task(answer=None, status='success')"
            if answer.strip().lower() in ("completed", "complete", "done", "")
            else f"apis.supervisor.complete_task(answer={answer!r}, status='success')")

        ev = world.evaluate().to_dict()

    passes, failures = len(ev.get("passes", [])), len(ev.get("failures", []))
    total = passes + failures or 1
    partial = round(passes / total, 3)
    colour = GREEN if ev.get("success") else RED

    print(f"\n{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}SCORE{RESET}  {colour}{partial}{RESET}  ({passes}/{total} requirements)  "
          f"success={ev.get('success')}")
    print(f"       delegations={log.delegations}  specialist_turns={log.specialist_turns}"
          f"  sandbox_refusals={log.blocked}")
    if partial == 0.333:
        print(f"       {DIM}that is exactly the do-nothing floor -- the episode "
              f"achieved nothing{RESET}")
    for f in ev.get("failures", []):
        head = str(f).split("\\n")[0][:100]
        print(f"  {RED}FAIL{RESET} {head}")


if __name__ == "__main__":
    main()
