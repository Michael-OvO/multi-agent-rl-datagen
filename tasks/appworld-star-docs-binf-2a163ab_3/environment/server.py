"""The sidecar: AppWorld, the specialists, and the oracle -- all outside the
Main's container.

The Main reaches this over HTTP and nothing else. It has no filesystem path to
AppWorld, to the specialists' code, to the task's ground truth, or to
`evaluate()`. "The Main has no API access" is therefore a fact about the
container topology rather than a promise in a prompt.

Two endpoints:
  POST /ask    {"specialist": ..., "brief": ...}  -> the specialist's report
  POST /done   {"answer": ...}                    -> submit, ends the episode
  GET  /state?token=...                           -> reward; 403 without the token

The token is generated at render time, written to `tests/verifier_token.txt`
(which Harbor uploads only at verification time) and passed to this process
through the sidecar's compose environment. Neither path enters the agent's image,
so during the agent phase there is no way to read the score -- which matters,
because `/state` would otherwise hand the Main the answer key.

Stdlib HTTP on purpose. An MCP server would add a dependency and buy typed tools
we do not need; the Main's surface is three verbs.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, "/opt/maf")  # forge/appworld/ lives here; see Dockerfile.sidecar

TASK_ID = os.environ["MAF_TASK_ID"]
CONFIG = json.loads(os.environ["MAF_CONFIG"])
PORT = int(os.environ.get("MAF_PORT", "8079"))

# Read once, then removed from the environment. `world.execute()` runs specialist
# code *in this process*, so anything left in `os.environ` is one `print` away
# from a specialist's transcript, and from there one report away from the Main --
# who could then simply GET /state and read the reward. `sandbox.py` refuses the
# code that would do it; this makes the environment not worth reading even if
# that gate is ever bypassed. TASK_ID and CONFIG stay: the Main is told its own
# task and `team roster` prints the roster, so neither is a secret.
TOKEN = os.environ.pop("MAF_VERIFIER_TOKEN")
_OPENAI_KEY = os.environ.pop("OPENAI_API_KEY", None)

ROSTER: list[str] = CONFIG["roster"]
TOPOLOGY: str = CONFIG["topology"]
VISIBILITY: str = CONFIG["visibility"]
BUDGET = CONFIG.get("delegation_budget")
SUB_MODEL = os.environ.get("MAF_SUB_MODEL", "gpt-4.1")


class Episode:
    """Holds the world, the ledger, and the budget. The Main cannot touch any of it."""

    def __init__(self) -> None:
        from appworld import AppWorld
        from openai import OpenAI

        self.world = AppWorld(task_id=TASK_ID, experiment_name="harbor",
                              ground_truth_mode="minimal")
        # Explicit, because the key is no longer in the environment for the
        # client to find on its own.
        self.client = OpenAI(api_key=_OPENAI_KEY)
        self.ledger: list[dict] = []
        self.delegations = 0
        self.done = False
        self.answer: str | None = None
        self._docs: dict | None = None

    @property
    def instruction(self) -> str:
        return self.world.task.instruction

    @property
    def docs(self) -> dict:
        """The roster's API catalogs, fetched once.

        These cannot change during an episode, and /roster is what the compose
        healthcheck polls every 3 seconds. Recomputing them per request made the
        probe a load generator against the same world the specialists use.
        """
        if self._docs is None:
            self._docs = {
                app: self.world.execute(
                    f"print(apis.api_docs.show_api_descriptions(app_name={app!r}))")
                for app in ROSTER
            }
        return self._docs

    def allowed_targets(self, sender: str) -> list[str]:
        if TOPOLOGY == "star":
            return ROSTER if sender == "main" else []
        if TOPOLOGY == "chain":
            if sender == "main":
                return ROSTER[:1]
            if sender in ROSTER:
                i = ROSTER.index(sender)
                return ROSTER[i + 1 : i + 2]
        return []

    def ask(self, specialist: str, brief: str) -> dict:
        if self.done:
            return {"error": "episode already finished"}
        allowed = self.allowed_targets("main")
        if specialist not in allowed:
            # Enforced here, not requested in the prompt.
            return {"error": f"you cannot reach {specialist!r}",
                    "allowed": allowed}
        if BUDGET is not None and self.delegations >= BUDGET:
            return {"error": "delegation budget exhausted", "budget": BUDGET}

        from forge.appworld.runtime import RunLog, run_specialist

        log = RunLog()
        report = run_specialist(self.client, self.world, specialist, brief, log,
                                model=SUB_MODEL)
        self.delegations += 1
        entry = {"specialist": specialist, "brief": brief, "report": report,
                 "specialist_turns": log.specialist_turns, "refused": log.refusals,
                 # Non-zero means this brief pushed the specialist outside its
                 # app and the sandbox stopped it. The Main writes the briefs.
                 "blocked": log.blocked,
                 # And *why*. A bare count once said the gate had refused
                 # something on a run that still scored 1.0, with no way to tell
                 # an injection from the gate obstructing correct work. It was
                 # the latter.
                 "blocked_reasons": log.blocked_reasons}
        self.ledger.append(entry)
        return {"report": report, "delegations_used": self.delegations,
                "budget": BUDGET}

    def finish(self, answer: str) -> dict:
        self.answer = answer
        self.done = True
        self.world.execute(_complete_call(answer))
        return {"ok": True}

    def state(self) -> dict:
        ev = self.world.evaluate().to_dict()
        failed = [str(f) for f in ev.get("failures", [])]
        passes, failures = len(ev.get("passes", [])), len(failed)
        total = passes + failures
        return {
            "success": bool(ev.get("success")),
            # AppWorld reports pass/fail per requirement; the partial score is a
            # count of its own unit tests, not a metric we invented.
            "partial": round(passes / total, 3) if total else 0.0,
            "passes": passes,
            "failures": failures,
            # The names, not just the count. A 5/6 that cannot say which 6th is
            # the outcome-only logging §7.4 keeps losing days to. /state is
            # token-gated and read after the episode, so this reaches the
            # verifier and never the Main.
            "failed": failed,
            "delegations": self.delegations,
            "answer": self.answer,
            "ledger": self.ledger,
        }


def _as_answer(answer: str):
    """AppWorld expects the task's own answer type, not prose.

    Action tasks ("like all the transactions...") return None in their ground
    truth; question tasks return a value. Submitting a prose summary makes the
    `assert answers match` requirement fail, which silently caps EVERY action
    task at 5/6 = 0.833 -- measured 2026-07-15: same work, prose answer -> 0.833,
    answer=None -> 1.000, success=True.

    The instruction tells the Main to say `completed` for action tasks. Honour it.
    """
    if answer.strip().lower() in ("completed", "complete", "done", ""):
        return None
    return answer


def _complete_call(answer: str) -> str:
    """Render the submission AppWorld actually receives.

    `repr` already produces bare `None` for None and a quoted literal for a
    string, so the conversion is entirely `_as_answer`'s. An earlier
    `.replace("'None'", "None")` here was vestigial -- it could not fire on the
    None path, and the one case it did fire on (a Main answering the literal
    string "None") was one it got wrong.
    """
    return f"apis.supervisor.complete_task(answer={_as_answer(answer)!r}, status='success')"


EPISODE: Episode | None = None


def _episode() -> Episode:
    """Return the initialized episode or fail loudly during invalid embedding."""
    if EPISODE is None:
        raise RuntimeError("sidecar episode has not been initialized")
    return EPISODE


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        """Keep routine HTTP access logs out of the experiment transcript."""
        return

    def _send(self, code: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict[str, object]:
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self) -> None:
        if self.path.startswith("/health"):
            # Deliberately touches nothing. This is what the compose healthcheck
            # polls; pointing it at /roster made every probe execute the API
            # catalog against the live world.
            #
            # This is single-threaded and /ask blocks for minutes, so probes
            # still queue behind a specialist and docker still gives up on them
            # (a BrokenPipeError per abandoned probe). That is now noise rather
            # than load: `depends_on: service_healthy` only gates startup, and
            # nothing here reaches the world. ThreadingHTTPServer would silence
            # it and put concurrent callers on a world that is not thread-safe,
            # which is a worse trade than a stray traceback.
            return self._send(200, {"ok": True})

        if self.path.startswith("/roster"):
            info = {"roster": ROSTER, "topology": TOPOLOGY,
                    "delegation_budget": BUDGET,
                    "instruction": _episode().instruction}
            if VISIBILITY == "docs":
                info["docs"] = _episode().docs
            return self._send(200, info)

        if self.path.startswith("/state"):
            # The score is behind the token. Without it the Main could read the
            # answer key mid-episode.
            token = ""
            if "?" in self.path:
                for part in self.path.split("?", 1)[1].split("&"):
                    if part.startswith("token="):
                        token = part[6:]
            if token != TOKEN:
                return self._send(403, {"error": "forbidden"})
            return self._send(200, _episode().state())

        self._send(404, {"error": "no such endpoint"})

    def do_POST(self) -> None:
        try:
            if self.path.startswith("/ask"):
                b = self._body()
                specialist = str(b.get("specialist", ""))
                brief = str(b.get("brief", ""))
                return self._send(200, _episode().ask(specialist, brief))
            if self.path.startswith("/done"):
                answer = str(self._body().get("answer", ""))
                return self._send(200, _episode().finish(answer))
            self._send(404, {"error": "no such endpoint"})
        except Exception:
            traceback.print_exc()
            self._send(500, {"error": "sidecar failure"})


if __name__ == "__main__":
    EPISODE = Episode()
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
