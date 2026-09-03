"""In-container verifier. Runs in `main` at verification time.

It computes nothing. It fetches the sidecar's terminal state -- which is
AppWorld's own `evaluate()`, a programmatic state check with no LLM in it that
also catches side effects -- and writes the reward out. There is no grading logic
here to get wrong, which is the point.

The token comes from `/tests`, which Harbor uploads only inside `verify()`
(`harbor/verifier/verifier.py:147`), after the agent phase. During the agent's
run this file does not exist, so the Main cannot read the score mid-episode.
"""

import json
import os
import traceback
import urllib.request

BASE = os.environ.get("MAF_ENV_URL", "http://maf-env:8079")
TOKEN_PATH = "/tests/verifier_token.txt"


def _write(reward, breakdown=None):
    os.makedirs("/logs/verifier", exist_ok=True)
    with open("/logs/verifier/reward.txt", "w") as fh:
        fh.write(str(float(reward)))
    if breakdown is not None:
        with open("/logs/verifier/breakdown.json", "w") as fh:
            json.dump(breakdown, fh, indent=1)


def main():
    with open(TOKEN_PATH) as fh:
        token = fh.read().strip()
    req = urllib.request.Request(f"{BASE}/state?token={token}")
    with urllib.request.urlopen(req, timeout=120) as r:
        state = json.loads(r.read())

    # Reward is AppWorld's verdict. `partial` is a count of its own per-
    # requirement unit tests, not a metric we invented; `success` is its own
    # all-requirements-met flag. We pick partial so the signal is graded rather
    # than binary, and gate on nothing of our own.
    reward = float(state.get("partial", 0.0))
    _write(reward, state)
    print("REWARD", reward, "| success", state.get("success"),
          "| delegations", state.get("delegations"))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Never swallow: a verifier that reports 0.0 on its own crash is
        # indistinguishable from an agent that failed.
        traceback.print_exc()
        _write(0.0, {"error": "verifier failed to reach the sidecar"})
        raise
