"""``theory-of-mind`` — interactive, multi-turn dimension.

Skill under test: **theory of mind + information-asymmetric communication**. The
agent must identify a culprit whose exonerating clues are held privately by
different witnesses. It cannot see the clues; it must ``ask`` the right witness.
Witnesses that do not hold a clue may know *who does* — a **referral** (2nd-order
ToM: reasoning about another agent's knowledge). Following a referral chain of
depth *d* reaches the clue-holder.

Cheaters lose by construction: ``budget = 2 * q_opt`` and every "dump" policy is
defined to spend its whole budget, so ``quality = q_opt/used <= 0.5 < tau`` even
when it guesses correctly. Only referral-following reaches the answer in q_opt
queries (quality 1.0).

Stdlib-only (copied into the task container).
"""

from __future__ import annotations

import random

from maf_core import RewardBreakdown, public, reward

NAME = "theory-of-mind"
CLI_NAME = "interview"
SUBMISSION_FILE = "/app/transcript.jsonl"
INTERACTIVE = True

DIFFICULTY_PRESETS = {
    "easy": {"suspects": 4, "referral_depth": 1},
    "medium": {"suspects": 5, "referral_depth": 2},
    "hard": {"suspects": 6, "referral_depth": 3},
}


# --------------------------------------------------------------------------- #
# Runtime state machine (the public interface)
# --------------------------------------------------------------------------- #
class Env:
    def __init__(self, instance: dict, state: dict | None = None):
        self.inst = instance
        self.asks = state["asks"] if state else 0
        self.transcript: list[dict] = []

    def state(self) -> dict:
        return {"asks": self.asks}

    def _rec(self, cmd, args, resp):
        self.transcript.append({"cmd": cmd, **args, "response": resp})
        return resp

    def handle(self, argv: list[str]) -> dict:
        cmd = argv[0] if argv else "help"
        if cmd == "agents":
            return self._rec("agents", {}, {
                "agents": self.inst["agents"],
                "suspects": self.inst["suspects"],
                "topics": self.inst["topics"],
                "entry": self.inst["entry"],
                "budget": self.inst["budget"]})
        if cmd == "ask":
            agent = argv[1] if len(argv) > 1 else None
            topic = argv[2] if len(argv) > 2 else None
            return self._rec("ask", {"agent": agent, "topic": topic},
                             self._ask(agent, topic))
        if cmd == "submit":
            ans = argv[1] if len(argv) > 1 else None
            correct = (ans == self.inst["_culprit"])
            return self._rec("submit", {"answer": ans}, {"correct": correct})
        return {"error": f"unknown command {cmd!r}"}

    def _ask(self, agent, topic) -> dict:
        if self.asks >= self.inst["budget"]:
            return {"result": "BUDGET_EXHAUSTED"}
        self.asks += 1
        chains = self.inst["_chains"]
        if topic not in chains:
            return {"result": "UNKNOWN_TOPIC"}
        chain = chains[topic]
        knower = chain[-1]
        if agent == knower:
            elim = self.inst["_elim"][topic]
            return {"result": "CLUE", "eliminates": elim,
                    "info": f"{elim} has a verified alibi and is not the culprit."}
        if agent in chain[:-1]:
            return {"result": "REFERRAL", "ask": chain[chain.index(agent) + 1]}
        return {"result": "NO_INFO"}


def make_env(instance: dict, state: dict | None = None) -> Env:
    return Env(instance, state)


# --------------------------------------------------------------------------- #
# Policies
# --------------------------------------------------------------------------- #
def _oracle(env: Env):
    meta = env.handle(["agents"])
    eliminated = set()
    for topic in meta["topics"]:
        agent = meta["entry"][topic]
        for _ in range(len(meta["agents"]) + 1):  # bounded referral walk
            r = env.handle(["ask", agent, topic])
            if r["result"] == "CLUE":
                eliminated.add(r["eliminates"])
                break
            if r["result"] == "REFERRAL":
                agent = r["ask"]
            else:
                break
    remaining = [s for s in meta["suspects"] if s not in eliminated]
    env.handle(["submit", remaining[0] if remaining else meta["suspects"][0]])


def _no_referral(env: Env):
    # Shortcut: ask each topic's entry agent once; ignore referrals.
    meta = env.handle(["agents"])
    eliminated = set()
    for topic in meta["topics"]:
        r = env.handle(["ask", meta["entry"][topic], topic])
        if r.get("result") == "CLUE":
            eliminated.add(r["eliminates"])
    remaining = [s for s in meta["suspects"] if s not in eliminated]
    env.handle(["submit", remaining[0] if remaining else meta["suspects"][0]])


def _info_dump(env: Env):
    # Shortcut: ask everyone about everything until the budget runs out.
    meta = env.handle(["agents"])
    eliminated = set()
    for a in meta["agents"]:
        for t in meta["topics"]:
            r = env.handle(["ask", a, t])
            if r.get("result") == "BUDGET_EXHAUSTED":
                return _submit_remaining(env, meta, eliminated)
            if r.get("result") == "CLUE":
                eliminated.add(r["eliminates"])
    _submit_remaining(env, meta, eliminated)


def _random_target(env: Env):
    # Shortcut: ask random (agent, topic) pairs until the budget runs out.
    meta = env.handle(["agents"])
    rng = random.Random(0)
    eliminated = set()
    while True:
        r = env.handle(["ask", rng.choice(meta["agents"]),
                        rng.choice(meta["topics"])])
        if r.get("result") == "BUDGET_EXHAUSTED":
            break
        if r.get("result") == "CLUE":
            eliminated.add(r["eliminates"])
    _submit_remaining(env, meta, eliminated)


def _submit_remaining(env, meta, eliminated):
    remaining = [s for s in meta["suspects"] if s not in eliminated]
    env.handle(["submit", remaining[0] if remaining else meta["suspects"][0]])


ORACLE = _oracle
CHEATERS = {
    "info_dump": _info_dump,
    "random_target": _random_target,
    "no_referral": _no_referral,
}


def run_policy(instance: dict, policy) -> list[dict]:
    env = make_env(instance, None)
    policy(env)
    return env.transcript


# --------------------------------------------------------------------------- #
# Verifier
# --------------------------------------------------------------------------- #
def verify(instance: dict, submission) -> RewardBreakdown:
    culprit = instance["_culprit"]
    q_opt = instance["_q_opt"]
    budget = instance["budget"]
    asks, answer = 0, None
    if isinstance(submission, list):
        for it in submission:
            if not isinstance(it, dict):
                continue
            if it.get("cmd") == "ask" and asks < budget:
                asks += 1
            elif it.get("cmd") == "submit":
                answer = it.get("answer")
    gate = 1 if answer == culprit else 0
    quality = min(1.0, q_opt / asks) if asks > 0 else 0.01
    return reward(gate, quality,
                  {"asks": asks, "q_opt": q_opt, "budget": budget,
                   "answer": answer, "culprit": culprit})


# --------------------------------------------------------------------------- #
# Generation
# --------------------------------------------------------------------------- #
def generate(seed: int, difficulty: dict) -> dict:
    rng = random.Random(seed)
    m = int(difficulty.get("suspects", 5))
    d = max(1, int(difficulty.get("referral_depth", 2)))

    suspects = [f"s{i}" for i in range(m)]
    culprit = rng.choice(suspects[1:])  # never s0, so guessers (who default to s0) fail
    non_culprits = [s for s in suspects if s != culprit]
    topics = [f"topic{i}" for i in range(len(non_culprits))]
    elim = {topics[i]: non_culprits[i] for i in range(len(non_culprits))}

    p = max(2 * (d + 1) + 2, d + 1)  # enough agents that budget < exhaustive
    agents = [f"a{i}" for i in range(p)]
    chains = {t: rng.sample(agents, d + 1) for t in topics}

    q_opt = sum(len(ch) for ch in chains.values())
    return {
        "suspects": suspects,
        "topics": topics,
        "agents": agents,
        "entry": {t: chains[t][0] for t in topics},
        "budget": 2 * q_opt,
        "_chains": chains,
        "_elim": elim,
        "_culprit": culprit,
        "_q_opt": q_opt,
    }


def ablate(instance: dict) -> dict:
    # Kill the information asymmetry: every topic's entry agent IS the knower
    # (depth 0), so a direct one-question-per-topic read solves it.
    chains = {t: [ch[-1]] for t, ch in instance["_chains"].items()}
    q_opt = sum(len(ch) for ch in chains.values())
    twin = dict(instance)
    twin["_chains"] = chains
    twin["entry"] = {t: chains[t][0] for t in chains}
    twin["_q_opt"] = q_opt
    twin["budget"] = 2 * q_opt
    return twin


def unique_ground_truth(instance: dict) -> bool:
    eliminated = set(instance["_elim"].values())
    remaining = [s for s in instance["suspects"] if s not in eliminated]
    return remaining == [instance["_culprit"]]


# --------------------------------------------------------------------------- #
# Instruction
# --------------------------------------------------------------------------- #
GOAL = (
    "You are the **Main agent** investigating who took the last cookie. Exactly "
    "one suspect is the culprit. The exonerating clues are held privately by "
    "different witnesses — you cannot see them. `ask` the right witness. A "
    "witness who lacks a clue may tell you **who to ask instead** (a referral). "
    "Follow referrals, gather the clues, deduce the culprit, and `submit` — all "
    "within your question budget."
)

OUTPUT_CONTRACT = (
    "Interact using the `interview` command (each call prints JSON):\n"
    "- `interview agents` — the witnesses, suspects, topics, per-topic entry "
    "witness, and your question budget.\n"
    "- `interview ask <witness> <topic>` — returns a CLUE (clears a suspect), a "
    "REFERRAL (`ask` someone else), or NO_INFO. Counts against your budget.\n"
    "- `interview submit <suspect>` — name the culprit.\n\n"
    "Score: 0 unless you name the correct culprit; otherwise "
    "`optimal_questions / your_questions` — so follow referrals to the clue-"
    "holders instead of interrogating everyone."
)


def render_instruction(instance: dict) -> str:
    pub = public(instance)
    lines = [f"## Suspects\n{', '.join(pub['suspects'])}"]
    lines.append(f"\n## Question budget\n{pub['budget']} questions")
    lines.append("\n## Topics and where to start (topic: entry witness)")
    for t in pub["topics"]:
        lines.append(f"- `{t}`: start by asking `{pub['entry'][t]}`")
    lines.append(f"\n## Witnesses\n{', '.join(pub['agents'])}")
    return "\n".join(lines)


class _TheoryOfMind:
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
    unique_ground_truth = staticmethod(unique_ground_truth)


DIM = _TheoryOfMind()
