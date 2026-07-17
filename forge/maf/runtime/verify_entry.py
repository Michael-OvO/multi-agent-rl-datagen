"""Generic in-container verifier — copied verbatim into each task's tests/verify.py.

Reads ``verify_config.json`` (written next to it by the Harbor renderer), loads
the full instance + the agent's submission, calls the copied dimension's
``verify``, and writes a float reward to ``/logs/verifier/reward.txt`` plus a
diagnostic breakdown. Stdlib-only. A verifier crash is written for diagnostics
and then re-raised so infrastructure failure cannot masquerade as agent reward 0.
"""

import json
import os
import sys
import traceback


def _load_submission(cfg):
    path = cfg["submission_path"]
    if not os.path.exists(path):
        return None
    if cfg["interactive"]:
        out = []
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        return out
    with open(path) as fh:
        return json.load(fh)


def _grade():
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "verify_config.json")) as fh:
        cfg = json.load(fh)
    sys.path.insert(0, "/tests/lib")
    import maf_dim  # noqa: E402  # pyright: ignore[reportMissingImports]

    with open(cfg["scenario_path"]) as fh:
        instance = json.load(fh)
    gt = cfg.get("ground_truth_path")
    if gt and os.path.exists(gt):
        with open(gt) as fh:
            instance.update(json.load(fh))

    submission = _load_submission(cfg)
    return maf_dim.verify(instance, submission)


def _write(reward, breakdown=None):
    os.makedirs("/logs/verifier", exist_ok=True)
    with open("/logs/verifier/reward.txt", "w") as fh:
        fh.write(str(float(reward)))
    if breakdown is not None:
        with open("/logs/verifier/breakdown.json", "w") as fh:
            json.dump(breakdown, fh)


if __name__ == "__main__":
    try:
        rb = _grade()
        _write(rb.reward, rb.to_json())
        print("REWARD", rb.reward)
    except Exception:
        traceback.print_exc()
        _write(0.0)
        raise
