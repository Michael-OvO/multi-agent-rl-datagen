"""The Gaia2 sidecar: the simulated world, the specialists, and the judge --
all outside the Main's container.

Same isolation argument as the AppWorld sidecar (see
forge/appworld/container/server.py): the Main reaches this over HTTP and
nothing else. It has no filesystem path to the scenario file, the oracle
events, the specialists, or the verdict. The one new surface is time --
Gaia2 scenarios schedule events on a simulated clock, so the protocol grows
a waiting verb:

  GET  /health                                     -> liveness, touches nothing
  GET  /roster                                     -> roster, instruction, clock
  POST /ask    {"specialist": ..., "brief": ...}   -> the specialist's report
  POST /wait   {"seconds": ...}                    -> jump the clock, return arrivals
  POST /done   {"answer": ...}                     -> report to the user; may continue
  GET  /state?token=...                            -> verdict; 403 without the token

/done is not always terminal: Gaia2 scenarios frequently schedule the next
user instruction to fire only after the agent reports back, so /done answers
either {"ok": true} or {"continued": true, "task": ...} -- the instruction
tells the Main to keep working in the second case. An answer beginning with
"FAIL" is the honest-failure channel: the user is told the truth and nothing
is faked; the write-action judge prices unmet oracle events identically
either way.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, "/opt/maf")  # forge/ lives here; see Dockerfile.sidecar

SCENARIO_PATH = os.environ.get("MAF_SCENARIO", "/opt/maf/scenario.json")
CONFIG = json.loads(os.environ["MAF_CONFIG"])
PORT = int(os.environ.get("MAF_PORT", "8080"))

# Read once, then removed: the sidecar's environment must not be worth
# reading. Specialists here cannot execute arbitrary code (they call typed
# app tools), so this is defence in depth rather than a live hole -- but the
# AppWorld sidecar popped it for a reason that was live, and two sidecars
# with different postures invite the wrong copy.
TOKEN = os.environ.pop("MAF_VERIFIER_TOKEN")
_OPENAI_KEY = os.environ.pop("OPENAI_API_KEY", None)

ROSTER: list[str] = CONFIG["roster"]
TOPOLOGY: str = CONFIG["topology"]
VISIBILITY: str = CONFIG["visibility"]
TARGET = CONFIG.get("delegation_target", CONFIG.get("delegation_budget"))

# The Main is Harbor's agent, outside this container; the compose file says
# what class it runs at so the parity rule can bind here too.
MAIN_MODEL = os.environ.get("MAF_MAIN_MODEL", "gpt-5.6-sol")
SUB_MODEL = os.environ.get("MAF_SUB_MODEL", "gpt-5.6-sol")

from forge.models import require_specialist_parity  # noqa: E402

# MAF_ALLOW_SUB_DOWNGRADE=1 is the explicit escape hatch: a below-class
# specialist is then a labelled experiment instead of a startup error.
require_specialist_parity(
    MAIN_MODEL, SUB_MODEL,
    allow_downgrade=os.environ.get("MAF_ALLOW_SUB_DOWNGRADE", "") == "1")

#: How long /done lingers for a scheduled follow-up turn, in simulated
#: seconds. Mirrors forge/gaia2/runtime.TURN_WAIT_SECONDS.
TURN_WAIT_SECONDS = 3600


class Episode:
    """Holds the world, ledger, and soft economy target outside the Main."""

    def __init__(self) -> None:
        from openai import OpenAI

        from forge.gaia2.are_world import open_world
        from forge.gaia2.runtime import EpisodeLog

        self.world = open_world(SCENARIO_PATH)
        self.client = OpenAI(api_key=_OPENAI_KEY)
        self.log = EpisodeLog()
        self.log.delegation_target = TARGET
        self.instruction = self.world.first_task() or "(the scenario sent no task)"
        self.done = False
        self.answer: str | None = None
        self._docs: dict | None = None

    @property
    def docs(self) -> dict:
        if self._docs is None:
            self._docs = {app: self.world.catalog(app) for app in ROSTER}
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

    def _arrivals(self) -> list[dict]:
        """Pending messages, delivered rather than dropped. A notification
        that arrives while a specialist works belongs to the Main."""
        return [{"kind": m.kind, "text": m.text} for m in self.world.drain()]

    def ask(self, specialist: str, brief: str) -> dict:
        if self.done:
            return {"error": "episode already finished"}
        allowed = self.allowed_targets("main")
        if specialist not in allowed:
            # Enforced here, not requested in the prompt.
            return {"error": f"you cannot reach {specialist!r}", "allowed": allowed}
        from forge.gaia2.runtime import (
            delegation_economy_features,
            run_specialist,
        )

        calls: list[dict] = []
        report = run_specialist(self.client, self.world, specialist, brief,
                                self.log, model=SUB_MODEL, calls_out=calls)
        self.log.delegations += 1
        self.log.event(self.world, "delegation", specialist=specialist,
                       brief=brief, report=report, calls=calls)
        economy = delegation_economy_features(
            TARGET, self.log.delegations)
        return {
            "report": report,
            "delegations_used": self.log.delegations,
            **economy,
            "target_is_hard_cap": False,
            "notifications": self._arrivals(),
        }

    def wait(self, seconds: int) -> dict:
        if self.done:
            return {"error": "episode already finished"}
        self.log.waits += 1
        arrived = [{"kind": m.kind, "text": m.text}
                   for m in self.world.wait(max(0, int(seconds)))]
        self.log.event(self.world, "wait", requested=int(seconds),
                       arrived=[a["text"] for a in arrived if a["kind"] != "stop"])
        return {"arrived": arrived, "sim_time": self.world.time_str()}

    def finish(self, answer: str) -> dict:
        surrender = answer.startswith("FAIL")
        if surrender:
            reason = answer.split("::", 1)[1].strip() if "::" in answer else answer
            self.world.send_user(f"I could not complete this task: {reason}")
            self.log.event(self.world, "surrender", reason=reason)
        else:
            self.world.send_user(answer)
            self.log.event(self.world, "done", answer=answer)
        self.answer = answer

        # The next user turn often fires only after the agent reports back.
        arrived = self.world.wait(TURN_WAIT_SECONDS)
        follow_up = next((m.text for m in arrived if m.kind == "user"), None)
        if follow_up is not None:
            self.log.user_turns += 1
            self.log.event(self.world, "user", content=follow_up)
            return {"continued": True, "task": follow_up}
        self.done = True
        return {"ok": True}

    def state(self) -> dict:
        from forge.gaia2.runtime import delegation_economy_features

        verdict = self.world.verdict()
        economy = delegation_economy_features(
            TARGET, self.log.delegations, task_success=verdict["success"])
        return {
            "success": verdict["success"],
            # Gaia2's official metric is per-scenario success; there is no
            # graded sub-score to pass through, so the reward is binary and
            # says so rather than inventing one.
            "partial": 1.0 if verdict["success"] else 0.0,
            "rationale": verdict["rationale"],
            "exception": verdict["exception"],
            "answer": self.answer,
            **self.log.as_dict(),
            **economy,
        }


EPISODE: Episode | None = None


def _episode() -> Episode:
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
            # Deliberately touches nothing; this is what the compose
            # healthcheck polls for the life of the episode.
            return self._send(200, {"ok": True})

        if self.path.startswith("/roster"):
            e = _episode()
            info = {"roster": ROSTER, "topology": TOPOLOGY,
                    "delegation_target": TARGET,
                    "target_is_hard_cap": False,
                    "instruction": e.instruction,
                    "sim_time": e.world.time_str()}
            if VISIBILITY == "docs":
                info["docs"] = e.docs
            return self._send(200, info)

        if self.path.startswith("/state"):
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
                return self._send(200, _episode().ask(
                    str(b.get("specialist", "")), str(b.get("brief", ""))))
            if self.path.startswith("/wait"):
                seconds = int(self._body().get("seconds", 0))  # type: ignore[arg-type]
                return self._send(200, _episode().wait(seconds))
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
