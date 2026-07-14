"""``failure-recovery`` — interactive, multi-turn dimension.

Skill under test: **dynamic replanning + failure recovery**. The agent dispatches
subtasks to workers via the ``coord`` CLI. The roster advertises which workers
*can attempt* a task, but success is hidden ground truth: some rostered workers
are decoys that fail. The agent must detect failures and re-route.

The optimum is the **canonical recovery strategy** (topological task order, try
rostered workers in sorted order, move on after a failure). ``quality =
D_opt / dispatches_used`` — so an honest agent that recovers efficiently reaches
1.0, while retrying a known-failed worker or brute-forcing everyone exhausts the
dispatch budget and fails the completion gate.

Stdlib-only (copied into the task container).
"""

from __future__ import annotations

import random

from forge.maf.core import RewardBreakdown, public, reward

NAME = "failure-recovery"
CLI_NAME = "coord"
SUBMISSION_FILE = "/app/transcript.jsonl"
INTERACTIVE = True

DIFFICULTY_PRESETS = {
    "easy": {"n": 4, "workers": 3, "fail_rate": 0.3},
    "medium": {"n": 5, "workers": 3, "fail_rate": 0.35},
    "hard": {"n": 7, "workers": 4, "fail_rate": 0.4},
}

_BIG_BUDGET = 10**6


# --------------------------------------------------------------------------- #
# Runtime state machine (the public interface)
# --------------------------------------------------------------------------- #
class Env:
    def __init__(self, instance: dict, state: dict | None = None):
        self.inst = instance
        self.done = set(state["done"]) if state else set()
        self.used = state["used"] if state else 0
        self.transcript: list[dict] = []

    def state(self) -> dict:
        return {"done": sorted(self.done), "used": self.used}

    def _rec(self, cmd, args, resp):
        self.transcript.append({"cmd": cmd, **args, "response": resp})
        return resp

    def handle(self, argv: list[str]) -> dict:
        cmd = argv[0] if argv else "help"
        if cmd == "roster":
            return self._rec("roster", {}, {"roster": self.inst["roster"]})
        if cmd == "dag":
            return self._rec("dag", {}, {"dag": self.inst["dag"]})
        if cmd == "status":
            pending = [t for t in self.inst["dag"] if t not in self.done]
            return self._rec("status", {}, {
                "done": sorted(self.done), "pending": pending,
                "dispatches_used": self.used, "budget": self.inst["_budget"]})
        if cmd == "dispatch":
            t = argv[1] if len(argv) > 1 else None
            w = argv[2] if len(argv) > 2 else None
            return self._rec("dispatch", {"task": t, "worker": w},
                             self._dispatch(t, w))
        if cmd == "submit":
            complete = self.done == set(self.inst["dag"])
            return self._rec("submit", {}, {"complete": complete,
                                            "done": sorted(self.done)})
        return {"error": f"unknown command {cmd!r}"}

    def _dispatch(self, t, w) -> dict:
        if self.used >= self.inst["_budget"]:
            return {"result": "ERROR", "reason": "budget exhausted"}
        self.used += 1
        dag, roster, succ = self.inst["dag"], self.inst["roster"], self.inst["_success"]
        if t not in dag:
            return {"result": "ERROR", "reason": "unknown task"}
        if w not in roster.get(t, []):
            return {"result": "ERROR", "reason": "worker not rostered for task"}
        if any(d not in self.done for d in dag[t]):
            return {"result": "ERROR", "reason": "dependencies not satisfied"}
        if t in self.done:
            return {"result": "ERROR", "reason": "task already complete"}
        if succ.get(f"{t}|{w}", False):
            self.done.add(t)
            return {"result": "SUCCESS"}
        return {"result": "FAILURE", "reason": "worker could not complete the task"}


def make_env(instance: dict, state: dict | None = None) -> Env:
    return Env(instance, state)


# --------------------------------------------------------------------------- #
# Policies
# --------------------------------------------------------------------------- #
def _oracle(env: Env):
    roster = env.handle(["roster"])["roster"]
    dag = env.handle(["dag"])["dag"]
    for t in _topo(dag):
        for w in sorted(roster[t]):
            if env.handle(["dispatch", t, w]).get("result") == "SUCCESS":
                break  # recovered / done; move to next task
    env.handle(["submit"])


def _static_plan(env: Env):
    # Shortcut: trust the roster, dispatch first worker once, never react.
    roster = env.handle(["roster"])["roster"]
    dag = env.handle(["dag"])["dag"]
    for t in _topo(dag):
        env.handle(["dispatch", t, sorted(roster[t])[0]])
    env.handle(["submit"])


def _retry_same(env: Env):
    # Shortcut: on failure, keep retrying the SAME worker.
    roster = env.handle(["roster"])["roster"]
    dag = env.handle(["dag"])["dag"]
    budget = env.handle(["status"])["budget"]
    for t in _topo(dag):
        w = sorted(roster[t])[0]
        for _ in range(budget + 1):
            r = env.handle(["dispatch", t, w])
            if r.get("result") in ("SUCCESS",) or r.get("reason") == "budget exhausted":
                break
    env.handle(["submit"])


def _brute_force(env: Env):
    # Shortcut: dispatch every task to every worker, ignore deps and failures.
    roster = env.handle(["roster"])["roster"]
    dag = env.handle(["dag"])["dag"]
    for t in sorted(dag):
        for w in sorted(roster[t]):
            env.handle(["dispatch", t, w])
    env.handle(["submit"])


ORACLE = _oracle
CHEATERS = {
    "static_plan": _static_plan,
    "retry_same": _retry_same,
    "brute_force": _brute_force,
}


def run_policy(instance: dict, policy) -> list[dict]:
    env = make_env(instance, None)
    policy(env)
    return env.transcript


# --------------------------------------------------------------------------- #
# Verifier
# --------------------------------------------------------------------------- #
def verify(instance: dict, submission) -> RewardBreakdown:
    dag = instance["dag"]
    roster = instance["roster"]
    succ = instance["_success"]
    budget = instance["_budget"]
    d_opt = instance["_d_opt"]
    try:
        done, used = _replay(submission, dag, roster, succ, budget)
    except Exception:
        done, used = set(), 0
    gate = 1 if done == set(dag) else 0
    quality = (d_opt / used) if used else 0.0
    subs = {"dispatches": used, "budget": budget, "d_opt": d_opt,
            "completed": len(done), "n_tasks": len(dag)}
    return reward(gate, quality, subs)


def _replay(submission, dag, roster, succ, budget):
    done, used = set(), 0
    if not isinstance(submission, list):
        return done, used
    for it in submission:
        if not isinstance(it, dict) or it.get("cmd") != "dispatch":
            continue
        if used >= budget:
            break
        used += 1
        t, w = it.get("task"), it.get("worker")
        if (t in dag and t not in done and w in roster.get(t, [])
                and all(d in done for d in dag[t])
                and succ.get(f"{t}|{w}", False)):
            done.add(t)
    return done, used


# --------------------------------------------------------------------------- #
# Generation (feasible-by-construction + planted decoys)
# --------------------------------------------------------------------------- #
def generate(seed: int, difficulty: dict) -> dict:
    rng = random.Random(seed)
    n = int(difficulty.get("n", 5))
    W = max(2, int(difficulty.get("workers", 3)))
    fail_rate = float(difficulty.get("fail_rate", 0.35))
    workers = [f"w{i}" for i in range(W)]

    tasks = [f"t{i}" for i in range(n)]
    dag = {}
    for i, t in enumerate(tasks):
        k = 0 if i == 0 else rng.randint(0, min(2, i))
        dag[t] = sorted(rng.sample(tasks[:i], k)) if k else []

    roster, success = {}, {}
    for t in tasks:
        size = rng.randint(2, W)
        rw = sorted(rng.sample(workers, size))
        roster[t] = rw
        # at least one worker succeeds; others fail with prob fail_rate
        good = rng.choice(rw)
        for w in rw:
            success[f"{t}|{w}"] = (w == good) or (rng.random() > fail_rate)

    # Force static_plan to fail on >=1 task: make its sorted-first worker a decoy.
    victim = tasks[rng.randrange(n)]
    first = roster[victim][0]
    others = [w for w in roster[victim] if w != first]
    if others:
        success[f"{victim}|{first}"] = False
        success[f"{victim}|{rng.choice(others)}"] = True

    inst = {"dag": dag, "roster": roster, "_success": success,
            "_budget": _BIG_BUDGET, "_d_opt": None}
    inst["_d_opt"] = _canonical_cost(inst)
    brute_cost = sum(len(roster[t]) for t in tasks)
    slack = max(1, (brute_cost - inst["_d_opt"]) // 3)
    inst["_budget"] = min(inst["_d_opt"] + slack, brute_cost - 1)
    inst["_budget"] = max(inst["_budget"], inst["_d_opt"])
    return inst


def _canonical_cost(instance: dict) -> int:
    tr = run_policy(instance, ORACLE)
    return sum(1 for it in tr if it["cmd"] == "dispatch")


# --------------------------------------------------------------------------- #
# Ablation twin + helpers
# --------------------------------------------------------------------------- #
def ablate(instance: dict) -> dict:
    # Remove all failures: every rostered worker succeeds. Then the static plan
    # (first worker, in order) completes with zero waste.
    twin = {
        "dag": {k: list(v) for k, v in instance["dag"].items()},
        "roster": {k: list(v) for k, v in instance["roster"].items()},
        "_success": {k: True for k in instance["_success"]},
        "_budget": _BIG_BUDGET,
        "_d_opt": None,
    }
    twin["_d_opt"] = _canonical_cost(twin)
    twin["_budget"] = twin["_d_opt"] + 2
    return twin


def _topo(dag):
    order, seen = [], set()

    def visit(t):
        if t in seen:
            return
        seen.add(t)
        for d in dag[t]:
            visit(d)
        order.append(t)

    for t in sorted(dag):
        visit(t)
    return order


GOAL = (
    "You are the **Main agent** coordinating a team of sub-agents. Dispatch every "
    "subtask to a worker via the `coord` CLI and drive them all to SUCCESS. The "
    "roster shows who *can attempt* each task, but some workers will **fail** — "
    "detect failures and re-route to another capable worker. You have a limited "
    "dispatch budget, so do not waste attempts."
)

OUTPUT_CONTRACT = (
    "Interact using the `coord` command (each call prints JSON):\n"
    "- `coord dag` — the subtask dependency graph.\n"
    "- `coord roster` — which workers may attempt each subtask.\n"
    "- `coord dispatch <task> <worker>` — attempt a subtask; returns SUCCESS / "
    "FAILURE / ERROR. A subtask may be dispatched only after its dependencies are "
    "done.\n"
    "- `coord status` — progress and remaining budget.\n"
    "- `coord submit` — finalize.\n\n"
    "Score: 0 unless every subtask is complete within budget; otherwise "
    "`optimal_dispatches / your_dispatches` — so recover efficiently and never "
    "retry a worker you have already seen fail."
)


def render_instruction(instance: dict) -> str:
    pub = public(instance)
    lines = ["## Subtasks (id: depends-on)"]
    for t in sorted(pub["dag"]):
        deps = ", ".join(pub["dag"][t]) if pub["dag"][t] else "—"
        lines.append(f"- `{t}`: deps={deps}")
    lines.append("\n## Roster (subtask: workers that may attempt it)")
    for t in sorted(pub["roster"]):
        lines.append(f"- `{t}`: {', '.join(pub['roster'][t])}")
    return "\n".join(lines)


class _FailureRecovery:
    NAME = NAME
    CLI_NAME = CLI_NAME
    SUBMISSION_FILE = SUBMISSION_FILE
    INTERACTIVE = INTERACTIVE
    DIFFICULTY_PRESETS = DIFFICULTY_PRESETS
    GOAL = GOAL
    OUTPUT_CONTRACT = OUTPUT_CONTRACT
    ORACLE = staticmethod(ORACLE)
    CHEATERS = CHEATERS
    generate = staticmethod(generate)
    make_env = staticmethod(make_env)
    run_policy = staticmethod(run_policy)
    verify = staticmethod(verify)
    ablate = staticmethod(ablate)
    render_instruction = staticmethod(render_instruction)


DIM = _FailureRecovery()
