"""Generic interactive CLI runtime — copied into each interactive task's lib/.

The task's ``coord``/``interview`` shim execs ``python3 /app/lib/cli.py <args>``.
Each invocation loads the full scenario + persisted state, applies one command
via the copied dimension's ``Env.handle``, persists state, appends the single
interaction to the transcript, and prints the public JSON response.

Stdlib-only. Ground-truth scenario lives outside /app (see the Dockerfile).
"""

import json
import os
import sys

SCENARIO = os.environ.get("MAF_SCENARIO", "/opt/maf/scenario.json")
STATE = os.environ.get("MAF_STATE", "/app/.maf_state.json")
TRANSCRIPT = os.environ.get("MAF_TRANSCRIPT", "/app/transcript.jsonl")


def main(argv):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import maf_dim

    instance = json.load(open(SCENARIO))
    state = json.load(open(STATE)) if os.path.exists(STATE) else None
    env = maf_dim.make_env(instance, state)
    resp = env.handle(argv)
    with open(STATE, "w") as fh:
        json.dump(env.state(), fh)
    with open(TRANSCRIPT, "a") as fh:
        fh.write(json.dumps(env.transcript[-1]) + "\n")
    print(json.dumps(resp))


if __name__ == "__main__":
    main(sys.argv[1:])
