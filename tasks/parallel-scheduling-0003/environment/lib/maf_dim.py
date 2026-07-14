"""``parallel-scheduling`` — static, single-shot dimension.

Skill under test: **dependency identification + parallel scheduling** (with a
capability-assignment trap). The agent reads a subtask DAG + a worker roster and
writes ``schedule.json`` minimizing makespan.

Construction guarantees the planted makespan equals the **critical-path length**,
which is a lower bound on any schedule's makespan — so the planted schedule is
provably optimal without solving an NP-hard problem. A capability trap makes a
greedy "earliest-free worker" policy block the critical chain.

Stdlib-only (this module is copied into the task container).
"""

from __future__ import annotations

import random

from maf_core import RewardBreakdown, public, reward

NAME = "parallel-scheduling"
SUBMISSION_FILE = "schedule.json"
INTERACTIVE = False

DIFFICULTY_PRESETS = {
    "easy": {"n": 4, "k": 2, "trap": True},
    "medium": {"n": 7, "k": 3, "trap": True},
    "hard": {"n": 10, "k": 4, "trap": True},
}


# --------------------------------------------------------------------------- #
# Generation (constructive — plant a provably optimal schedule)
# --------------------------------------------------------------------------- #
def generate(seed: int, difficulty: dict) -> dict:
    rng = random.Random(seed)
    n = int(difficulty.get("n", 7))
    k = max(2, int(difficulty.get("k", 3)))
    trap = bool(difficulty.get("trap", True))

    chain_len = max(2, min(n - 1, n // 2 + 1))
    chain_durs = [rng.randint(2, 3) for _ in range(chain_len)]
    cp = sum(chain_durs)  # critical-path length == optimal makespan

    workers: dict[str, list[str]] = {}
    # w0 = bottleneck B: the ONLY tester, but also a coder (this is the trap).
    workers["w0"] = ["test", "code"]
    for c in range(1, k):
        workers[f"w{c}"] = ["code"]

    subtasks: dict[str, dict] = {}
    planted: list[dict] = []

    # Critical chain of "test" tasks — only w0 can run them, back to back.
    t = 0
    prev = None
    chain_ids = []
    for i in range(chain_len):
        tid = f"t1{i:02d}"  # ids after the bait so the bait sorts first
        deps = [prev] if prev else []
        subtasks[tid] = {"skill": "test", "dur": chain_durs[i], "deps": deps}
        planted.append({"subtask": tid, "worker": "w0", "start": t})
        t += chain_durs[i]
        prev = tid
        chain_ids.append(tid)

    # Bait task (smallest id) — a big code task runnable by w0 or a coder.
    # A greedy "earliest-free (tie: lowest id)" policy assigns it to w0 and
    # blocks the whole test chain.
    if trap and k >= 2:
        subtasks["t000"] = {"skill": "code", "dur": cp, "deps": []}
        planted.append({"subtask": "t000", "worker": "w1", "start": 0})

    # Side code tasks fill remaining coders in parallel within [0, cp].
    n_have = len(subtasks)
    side_coders = [f"w{c}" for c in range(2, k)]  # w1 holds the bait
    si = 0
    for coder in side_coders:
        used = 0
        while n_have < n:
            dur = rng.randint(2, 3)
            if used + dur > cp:
                break
            deps = []
            if si > 0 and f"t2{si-1:02d}" in subtasks:
                # chain side tasks on the same coder to bound concurrency
                prev_side = f"t2{si-1:02d}"
                if planted_worker(planted, prev_side) == coder:
                    deps = [prev_side]
            tid = f"t2{si:02d}"
            subtasks[tid] = {"skill": "code", "dur": dur, "deps": deps}
            planted.append({"subtask": tid, "worker": coder, "start": used})
            used += dur
            si += 1
            n_have += 1

    inst = {
        "workers": workers,
        "subtasks": subtasks,
        "_planted": planted,
        "_opt_makespan": _makespan(planted, subtasks),
    }
    return inst


def planted_worker(planted: list[dict], tid: str):
    for e in planted:
        if e["subtask"] == tid:
            return e["worker"]
    return None


# --------------------------------------------------------------------------- #
# Policies (oracle + cheaters). Cheaters read only public fields.
# --------------------------------------------------------------------------- #
def _oracle(instance: dict) -> list[dict]:
    # Constructive oracle: replay the planted optimal schedule.
    return [dict(e) for e in instance["_planted"]]


def _serial(instance: dict) -> list[dict]:
    # Shortcut: never parallelize. Run every task back-to-back in topo order.
    order = _topo_order(instance["subtasks"])
    schedule, t = [], 0
    for tid in order:
        w = _first_capable(instance, tid)
        schedule.append({"subtask": tid, "worker": w, "start": t})
        t += instance["subtasks"][tid]["dur"]
    return schedule


def _greedy_earliest(instance: dict) -> list[dict]:
    # Shortcut: list-schedule; pick the lowest-id ready task, assign to the
    # capable worker free earliest (tie: lowest worker id). No lookahead.
    subs = instance["subtasks"]
    finish: dict[str, int] = {}
    free: dict[str, int] = {w: 0 for w in instance["workers"]}
    schedule = []
    remaining = set(subs)
    while remaining:
        ready = sorted(
            t for t in remaining if all(d in finish for d in subs[t]["deps"])
        )
        tid = ready[0]
        skill = subs[tid]["skill"]
        capable = sorted(w for w, sk in instance["workers"].items() if skill in sk)
        w = min(capable, key=lambda x: (free[x], x))
        dep_ready = max((finish[d] for d in subs[tid]["deps"]), default=0)
        start = max(free[w], dep_ready)
        end = start + subs[tid]["dur"]
        schedule.append({"subtask": tid, "worker": w, "start": start})
        free[w] = end
        finish[tid] = end
        remaining.discard(tid)
    return schedule


ORACLE = _oracle
CHEATERS = {"serial": _serial, "greedy_earliest": _greedy_earliest}


def run_policy(instance: dict, policy) -> list[dict]:
    return policy(instance)


# --------------------------------------------------------------------------- #
# Verifier
# --------------------------------------------------------------------------- #
def verify(instance: dict, submission) -> RewardBreakdown:
    subs = instance["subtasks"]
    workers = instance["workers"]
    opt = instance["_opt_makespan"]
    try:
        gate, makespan = _check_schedule(submission, subs, workers)
    except Exception:
        gate, makespan = False, None
    if not gate:
        return reward(0, 0.01, {"makespan": makespan, "opt_makespan": opt})
    quality = opt / makespan if makespan else 0.0
    return reward(1, quality, {"makespan": makespan, "opt_makespan": opt})


def _check_schedule(submission, subs, workers):
    if not isinstance(submission, list):
        return False, None
    seen = {}
    for e in submission:
        if not isinstance(e, dict):
            return False, None
        tid, w, start = e.get("subtask"), e.get("worker"), e.get("start")
        if tid not in subs or w not in workers or not isinstance(start, int):
            return False, None
        if start < 0 or tid in seen:
            return False, None
        if subs[tid]["skill"] not in workers[w]:
            return False, None
        seen[tid] = (w, start, start + subs[tid]["dur"])
    if set(seen) != set(subs):  # every subtask scheduled exactly once
        return False, None
    for tid, (_, start, _end) in seen.items():
        for d in subs[tid]["deps"]:
            if seen[d][2] > start:  # dep must finish by task start
                return False, None
    # no worker runs two tasks at once
    by_worker: dict[str, list] = {}
    for tid, (w, start, end) in seen.items():
        by_worker.setdefault(w, []).append((start, end))
    for iv in by_worker.values():
        iv.sort()
        for a, b in zip(iv, iv[1:]):
            if a[1] > b[0]:
                return False, None
    makespan = max(end for _, _, end in seen.values())
    return True, makespan


def _makespan(schedule, subs):
    return max(e["start"] + subs[e["subtask"]]["dur"] for e in schedule)


# --------------------------------------------------------------------------- #
# Ablation twin + uniqueness
# --------------------------------------------------------------------------- #
def ablate(instance: dict) -> dict:
    # Remove all parallelism: linearize into one chain. Then serial == optimal.
    order = _topo_order(instance["subtasks"])
    subs = {}
    planted, t, prev = [], 0, None
    for tid in order:
        old = instance["subtasks"][tid]
        subs[tid] = {"skill": old["skill"], "dur": old["dur"],
                     "deps": [prev] if prev else []}
        w = _first_capable(instance, tid)
        planted.append({"subtask": tid, "worker": w, "start": t})
        t += old["dur"]
        prev = tid
    return {
        "workers": dict(instance["workers"]),
        "subtasks": subs,
        "_planted": planted,
        "_opt_makespan": t,
    }


def unique_ground_truth(instance: dict) -> bool:
    # The optimum value is well-defined iff the planted makespan equals the
    # critical-path lower bound (a bound no schedule can beat).
    return instance["_opt_makespan"] == _critical_path(instance["subtasks"])


def _critical_path(subs) -> int:
    order = _topo_order(subs)
    es = {}
    for tid in order:
        es[tid] = max((es[d] + subs[d]["dur"] for d in subs[tid]["deps"]), default=0)
    return max(es[t] + subs[t]["dur"] for t in subs)


# --------------------------------------------------------------------------- #
# Helpers + instruction
# --------------------------------------------------------------------------- #
def _topo_order(subs):
    order, seen = [], set()

    def visit(t):
        if t in seen:
            return
        seen.add(t)
        for d in subs[t]["deps"]:
            visit(d)
        order.append(t)

    for t in sorted(subs):
        visit(t)
    return order


def _first_capable(instance, tid):
    skill = instance["subtasks"][tid]["skill"]
    for w in sorted(instance["workers"]):
        if skill in instance["workers"][w]:
            return w
    raise ValueError(f"no worker can do {tid}")


def render_instruction(instance: dict) -> str:
    pub = public(instance)
    lines = ["## Team roster (worker: skills)"]
    for w in sorted(pub["workers"]):
        lines.append(f"- `{w}`: {', '.join(pub['workers'][w])}")
    lines.append("\n## Subtasks (id: skill, duration, depends-on)")
    for t in sorted(pub["subtasks"]):
        s = pub["subtasks"][t]
        deps = ", ".join(s["deps"]) if s["deps"] else "—"
        lines.append(f"- `{t}`: skill={s['skill']}, dur={s['dur']}, deps={deps}")
    return "\n".join(lines)


GOAL = (
    "You are the **Main agent** coordinating a team of specialist sub-agents. "
    "Produce an execution schedule that assigns every subtask to a worker and a "
    "start time, **minimizing the overall finish time (makespan)**."
)

OUTPUT_CONTRACT = (
    "Write your schedule to `/app/schedule.json` — a JSON array of objects "
    '`{"subtask": "<id>", "worker": "<id>", "start": <int>}`.\n\n'
    "Rules (any violation scores 0):\n"
    "- Schedule every subtask exactly once.\n"
    "- A subtask may start only after all its dependencies have finished.\n"
    "- A worker may only run a task whose skill it has.\n"
    "- A worker runs one task at a time (no overlapping intervals).\n\n"
    "Your score is `optimal_makespan / your_makespan` — so parallelize "
    "independent work across the team."
)


class _Scheduling:
    NAME = NAME
    SUBMISSION_FILE = SUBMISSION_FILE
    INTERACTIVE = INTERACTIVE
    DIFFICULTY_PRESETS = DIFFICULTY_PRESETS
    GOAL = GOAL
    OUTPUT_CONTRACT = OUTPUT_CONTRACT
    ORACLE = staticmethod(ORACLE)
    CHEATERS = CHEATERS
    generate = staticmethod(generate)
    run_policy = staticmethod(run_policy)
    verify = staticmethod(verify)
    ablate = staticmethod(ablate)
    render_instruction = staticmethod(render_instruction)
    unique_ground_truth = staticmethod(unique_ground_truth)

    def make_env(self, instance):  # static dimension has no interactive env
        raise NotImplementedError("scheduling is single-shot; no Env")


DIM = _Scheduling()
