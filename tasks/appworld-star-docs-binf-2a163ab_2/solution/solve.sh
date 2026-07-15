#!/bin/bash
# The reference orchestration: the decomposition a competent Main would find.
#
# This is NOT a replay. The specialists are real LLMs and do the actual work;
# what is recorded here is only the part the Main is measured on -- noticing that
# `phone` holds a fact `venmo` needs, and carrying it across. Everything else is
# still done live.
#
# So this oracle is probabilistic, not deterministic: it needs OPENAI_API_KEY at
# verification time, it costs tokens, and a bad specialist turn can fail it. That
# is a real cost, and it buys the only thing an oracle is for -- evidence the
# task is solvable, so that a failing Main is failing at orchestration rather
# than fighting a broken harness. See forge/appworld/reference.py.
set -euo pipefail

python3 - <<'MAF_SOLVE_EOF'
import json
import subprocess
import sys

STEPS = [
    {
        "specialist": "phone",
        "brief": "List the full names of all of my siblings -- only the contacts whose relationship to me is 'sibling', not my other contacts. Page through every page of the contact search (keep increasing page_index until a page comes back empty) so you do not miss any."
    },
    {
        "specialist": "venmo",
        "brief": "On my Venmo social feed, find every transaction from yesterday that involves any of these people: {prev}. Page through the ENTIRE social feed first -- keep increasing page_index until a page comes back empty -- and collect every matching transaction before you like anything. Then like every one of them. Report how many you liked."
    }
]
ANSWER = "completed"


def team(*args):
    p = subprocess.run(["team", *args], capture_output=True, text=True)
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError:
        sys.exit(f"team {args[0]} returned no JSON: {p.stdout!r} {p.stderr!r}")


prev = ""
for step in STEPS:
    reply = team("ask", step["specialist"], step["brief"].replace("{prev}", prev))
    if "report" not in reply:
        sys.exit(f"{step['specialist']} failed: {reply}")
    prev = reply["report"]
    print(f"{step['specialist']}: {prev}", file=sys.stderr)

team("done", ANSWER)
MAF_SOLVE_EOF
