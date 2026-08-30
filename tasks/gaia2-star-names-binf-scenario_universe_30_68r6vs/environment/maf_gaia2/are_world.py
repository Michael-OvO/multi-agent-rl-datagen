# pyright: reportMissingImports=false
"""The World adapter over Meta's Agents Research Environments harness.

`forge/gaia2/runtime.py` speaks to a duck-typed world; this module is the one
place that world becomes the official harness (the
`meta-agents-research-environments` package, import name `are.simulation`).
The harness needs pydantic 2 and the pinned main environment carries
AppWorld's pydantic 1, so this module only imports where the harness is
installed -- `.venv-gaia2` locally, the sidecar image in a shipped task --
and `forge/tests` never touches it. That is also why the import sits at the
top with a pyright silence instead of behind a try: an ImportError here
should name the missing package loudly, not degrade.

What the adapter maps, official mechanism -> World method:

    scenario JSON (the fetched trace files)   -> open_world()
      JsonScenarioImporter + preprocess_scenario: the oracle run happens
      inside preprocess, the judge attaches to the scenario, turns
      initialize with the judge's trigger condition -- the same path the
      official benchmark takes, so the verdict is Gaia2's own.
    scenario.get_tools() grouped by app_name  -> catalog(), call()
      The app boundary is membership in the specialist's group. A call to a
      tool owned by another app is refused with the owner named, before
      anything executes.
    SystemApp__wait_for_notification          -> wait()
      The official waiting feature: jumps simulated time to the next
      scheduled event or the timeout, whichever is first. Called as the app
      tool so the event log records the wait exactly as the official agent's
      would.
    notification_system.message_queue         -> drain()
      USER_MESSAGE / ENVIRONMENT_NOTIFICATION / ENVIRONMENT_STOP by
      simulated timestamp, mapped to runtime `Msg` kinds.
    AgentUserInterface__send_message_to_user  -> send_user()

The judge defaults to `ScriptedGraphPerEventJudgeConfig`: the official graph
judge with the LLM soft-checkers deactivated -- deterministic and free. The
2026-07-28 audit measured what that trade costs: paraphrased-but-correct
message content hard-fails (a false negative on an otherwise gold-matching
episode), and 32 of the 37 seamful scenarios are reply-conditioned -- their
later phases schedule only when the judge's turn condition matches, so the
scripted judge freezes them mid-episode. `open_world(judge_model=...)`
therefore runs Gaia2's official judge exactly as shipped -- graph judge plus
LLM soft-checkers -- with the named model as the checker. Neither
configuration modifies the judge; they are both Gaia2's own.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from are.simulation.agents.are_simulation_agent_config import LLMEngineConfig
from are.simulation.data_handler.importer import JsonScenarioImporter
from are.simulation.environment import Environment, EnvironmentConfig
from are.simulation.notification_system import MessageType, VerboseNotificationSystem
from are.simulation.scenarios.scenario_imported_from_json.utils import (
    preprocess_scenario,
)
from are.simulation.types import EnvironmentType
from are.simulation.validation.configs import (
    GraphPerEventJudgeConfig,
    ScriptedGraphPerEventJudgeConfig,
    create_judge_engine,
)

from forge.gaia2.runtime import Msg, describe_tool

#: Apps that are runtime plumbing, never a specialist role. Mirrors
#: forge/gaia2/mine.py's _INFRA_APPS -- kept as literals here because this
#: module must stay importable without dragging the miner into the sidecar.
_INFRA_APPS = frozenset({"AgentUserInterface", "SystemApp"})

_SEND_TO_USER = "AgentUserInterface__send_message_to_user"
_WAIT = "SystemApp__wait_for_notification"

#: Simulated seconds held back from every wait so our own waiting can never
#: end the world. See AreWorld.wait for the measurement that earned this.
WAIT_RESERVE_SECONDS = 10

_KIND = {
    MessageType.USER_MESSAGE: "user",
    MessageType.ENVIRONMENT_NOTIFICATION: "notification",
    MessageType.ENVIRONMENT_STOP: "stop",
}


def _render_result(result) -> str:
    if result is None:
        return "OK (no return value)"
    if isinstance(result, str):
        return result
    try:
        return json.dumps(result, default=str, indent=1)
    except (TypeError, ValueError):
        return str(result)




class AreWorld:
    """One live scenario: the environment thread, its tools, and its judge."""

    def __init__(self, scenario, env):
        self.scenario = scenario
        self.env = env
        # All user messages reach the Main as notifications; blocking a send
        # on interactive input would hang the episode. Same setting the
        # official agent applies before its loop.
        env.get_app("AgentUserInterface").wait_for_user_response = False

        self._tools: dict[str, Any] = {t.name: t for t in scenario.get_tools()}
        self._owner: dict[str, str] = {t.name: t.app_name for t in scenario.get_tools()}
        self._by_app: dict[str, list] = {}
        for t in scenario.get_tools():
            if t.app_name not in _INFRA_APPS:
                self._by_app.setdefault(t.app_name, []).append(t)

    # -- World interface ----------------------------------------------------

    def time_str(self) -> str:
        stamp = self.env.time_manager.time()
        return datetime.fromtimestamp(stamp, tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S")

    def catalog(self, app: str) -> str:
        tools = self._by_app.get(app)
        if not tools:
            return f"(no tools: {app!r} is not an app in this scenario)"
        # describe_tool renders argument descriptions too -- they carry the
        # valid enum values and formats (see its docstring for the bug this
        # fixed).
        return "\n".join(describe_tool(t) for t in tools)

    def call(self, apps, tool: str, args: dict) -> tuple[str, str]:
        """Execute one tool call for a holder of `apps`. -> (text, status).

        status: "ok" | "error" | "refused". The boundary decision happens
        here, before execution, and the refusal names the owning app so the
        trajectory shows which brief walked out of bounds.
        """
        allowed = tuple(apps)
        owner = self._owner.get(tool)
        if owner is None:
            known = sorted(t for a in allowed for t in
                           (x.name for x in self._by_app.get(a, ())))
            return (f"unknown tool {tool!r}; your tools are: {', '.join(known)}",
                    "error")
        if owner in _INFRA_APPS or owner not in allowed:
            return (f"{tool} belongs to {owner}, which you cannot use", "refused")
        try:
            result = self._tools[tool](**args)
        except Exception as e:  # noqa: BLE001 -- the world's errors are feedback
            return f"{type(e).__name__}: {e}", "error"
        return _render_result(result), "ok"

    def drain(self) -> list[Msg]:
        now = datetime.fromtimestamp(self.env.time_manager.time(), tz=timezone.utc)
        messages = self.env.notification_system.message_queue.get_by_timestamp(now)
        return [Msg(kind=_KIND[m.message_type], text=m.message) for m in messages]

    def remaining(self) -> float:
        """Simulated seconds before the world stops; inf when unbounded.

        The environment ends once `duration` simulated seconds pass, and
        every Gaia2 scenario ships duration=1000. Nothing told the agent
        that, and nothing clamped our waits to it.
        """
        duration = getattr(self.env, "duration", None)
        if duration is None:
            return float("inf")
        return max(0.0, duration - self.env.time_manager.time_passed())

    def wait(self, seconds: int) -> list[Msg]:
        """Advance simulated time, never past the world's own horizon.

        Measured 2026-07-30 over the first full campaign: 73% of all cells
        (108 of 147) were killed by an environment stop before the agent
        could conclude, 93 of them immediately after a 3600-second wait
        against a 1000-second world -- and not one successful cell ever hit
        such a stop. Our own wait cap was ending the episodes we were
        trying to measure, evenly across every configuration, which is why
        it read as uniform difficulty rather than as a bug.
        """
        budget = self.remaining() - WAIT_RESERVE_SECONDS
        clamped = int(max(0, min(int(seconds), budget)))
        self._tools[_WAIT](timeout=clamped)
        return self.drain()

    def send_user(self, text: str) -> None:
        self._tools[_SEND_TO_USER](content=text)

    # -- episode lifecycle --------------------------------------------------

    def first_task(self, timeout: int = 900) -> str | None:
        """The opening user message. Scenarios deliver it as a scheduled
        event shortly after start; None means the world never spoke."""
        arrived = self.drain() or self.wait(timeout)
        for m in arrived:
            if m.kind == "user":
                return m.text
        return None

    def verdict(self) -> dict:
        result = self.scenario.validate(self.env)
        return {
            "success": bool(result.success),
            "rationale": result.rationale,
            "exception": None if result.exception is None else repr(result.exception),
        }

    def clock_facts(self) -> dict:
        """The world's clock and state, stamped on every stop row.

        Recorded rather than assumed, because the horizon is not the wall
        the name suggests. `Environment._time_based_loop` advances the
        simulated clock on a *real* timer in a background thread -- one
        `tick()`, one `time.sleep(1)`, then `time_increment_in_seconds - 1`
        added -- so the 1000-simulated-second horizon every scenario carries
        is spent in real time whether or not the agent is doing anything.
        Every second a model spends thinking, and every second of 429
        backoff, comes out of it. That makes `time_passed` at the stop the
        difference between an episode that ran out of task and one that ran
        out of clock while queued, and the two were previously the same row.

        `remaining` is None rather than `inf` because the trajectory is
        written as JSON, which has no infinity -- `remaining()` is infinite
        only for a world that declares no duration.
        """
        remaining = self.remaining()
        state = getattr(self.env, "state", None)
        return {
            "duration": getattr(self.env, "duration", None),
            "time_passed": round(float(self.env.time_manager.time_passed()), 1),
            "remaining": None if remaining == float("inf") else round(remaining, 1),
            "env_state": str(getattr(state, "value", state)),
        }

    def stop(self) -> None:
        self.env.stop()


def open_world(scenario_path: str | Path, judge_model: str | None = None) -> AreWorld:
    """Load one fetched scenario file and start its environment.

    `judge_model=None` (default) attaches the deterministic scripted judge;
    a model name attaches Gaia2's official judge as shipped, with that model
    (OpenAI provider, key from the environment) running the soft checkers.
    The choice also shapes episode *dynamics* on reply-conditioned
    scenarios -- see the module docstring.

    The oracle run, judge attachment and turn initialization all happen in
    the official `preprocess_scenario`; by the time this returns, the
    environment thread is live and the first user turn is scheduled.
    """
    if judge_model is None:
        judge_config = ScriptedGraphPerEventJudgeConfig()
    else:
        judge_config = GraphPerEventJudgeConfig(engine=create_judge_engine(
            LLMEngineConfig(model_name=judge_model, provider="openai",
                            endpoint=None)))
    raw = Path(scenario_path).read_text()
    scenario, _completed, _logs = JsonScenarioImporter().import_from_json_to_benchmark(
        raw, load_completed_events=False)
    preprocess_scenario(scenario, judge_config=judge_config,
                        offline_validation=False)
    config = EnvironmentConfig(
        oracle_mode=False,
        queue_based_loop=False,
        time_increment_in_seconds=scenario.time_increment_in_seconds,
        exit_when_no_events=False,
    )
    if scenario.start_time and scenario.start_time > 0:
        config.start_time = scenario.start_time
    env = Environment(
        environment_type=EnvironmentType.CLI,
        config=config,
        notification_system=VerboseNotificationSystem(),
    )
    env.run(scenario, wait_for_end=False)
    return AreWorld(scenario, env)
