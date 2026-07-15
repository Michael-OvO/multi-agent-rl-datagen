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
TOKEN = os.environ["MAF_VERIFIER_TOKEN"]
PORT = int(os.environ.get("MAF_PORT", "8079"))

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
        self.client = OpenAI()
        self.ledger: list[dict] = []
        self.delegations = 0
        self.done = False
        self.answer: str | None = None

    @property
    def instruction(self) -> str:
        return self.world.task.instruction

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
                 "specialist_turns": log.specialist_turns, "refused": log.refusals}
        self.ledger.append(entry)
        return {"report": report, "delegations_used": self.delegations,
                "budget": BUDGET}

    def finish(self, answer: str) -> dict:
        self.answer = answer
        self.done = True
        self.world.execute(
            f"apis.supervisor.complete_task(answer={_as_answer(answer)!r}, "
            "status='success')".replace("'None'", "None"))
        return {"ok": True}

    def state(self) -> dict:
        ev = self.world.evaluate().to_dict()
        passes, failures = len(ev.get("passes", [])), len(ev.get("failures", []))
        total = passes + failures
        return {
            "success": bool(ev.get("success")),
            # AppWorld reports pass/fail per requirement; the partial score is a
            # count of its own unit tests, not a metric we invented.
            "partial": round(passes / total, 3) if total else 0.0,
            "passes": passes,
            "failures": failures,
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


EPISODE: Episode | None = None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # keep the sidecar quiet
        pass

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        if self.path.startswith("/roster"):
            info = {"roster": ROSTER, "topology": TOPOLOGY,
                    "delegation_budget": BUDGET,
                    "instruction": EPISODE.instruction}
            if VISIBILITY == "docs":
                info["docs"] = {
                    app: EPISODE.world.execute(
                        f"print(apis.api_docs.show_api_descriptions(app_name={app!r}))")
                    for app in ROSTER
                }
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
            return self._send(200, EPISODE.state())

        self._send(404, {"error": "no such endpoint"})

    def do_POST(self):
        try:
            if self.path.startswith("/ask"):
                b = self._body()
                return self._send(200, EPISODE.ask(b.get("specialist", ""),
                                                   b.get("brief", "")))
            if self.path.startswith("/done"):
                return self._send(200, EPISODE.finish(str(self._body().get("answer", ""))))
            self._send(404, {"error": "no such endpoint"})
        except Exception:
            traceback.print_exc()
            self._send(500, {"error": "sidecar failure"})


if __name__ == "__main__":
    EPISODE = Episode()
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
