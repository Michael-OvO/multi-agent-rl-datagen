"""The Main and the app specialists, over a Gaia2 world.

This is the runtime `render.py` was waiting for: the same three-verb contract
as `forge/appworld/runtime.py` -- DELEGATE, DONE, FAIL -- pointed at Meta's
Agents Research Environments (the simulation platform Gaia2 ships on) instead
of AppWorld's python shell. Two mechanical differences, one new capability:

  * **Tools, not code.** An Agents Research Environments app exposes typed
    functions, so a specialist issues one `CALL <tool> :: {json args}` per
    turn instead of a fenced python block. The app boundary is structural --
    the world refuses a call outside the specialist's app -- so there is no
    code gate to run; the refusal is still counted and named, because the
    Main writes the briefs and a brief that talks a specialist out of bounds
    is worth reading about.

  * **The judge is Gaia2's own.** Write-action verification against the
    scenario's oracle events, reached through `world.verdict()`. Nothing
    here touches it.

  * **Time is real (simulated).** Scenarios schedule events -- a reply
    arriving, a cab confirming -- at future simulated times. The official
    harness exposes waiting as a tool (`SystemApp__wait_for_notification`);
    here it is a Main verb, `WAIT <seconds>`, because *when to stop acting
    and wait* is a coordination decision and the Main is the model under
    test. A wait jumps simulated time to the next event or the timeout,
    whichever is first, and whatever arrived is delivered before the Main's
    next step. Notifications also arrive unprompted between steps; delivery
    is the runtime's job, deciding what to do about them is the Main's.

The honest-failure channel ports unchanged in spirit: FAIL sends the user a
truthful "I could not complete this" and stops -- no writes are faked, and
the write-action judge prices an unmet oracle event the same whether the
agent lied about it or admitted it. The admission rule from the honesty probe
still applies: before any Gaia2 family ships, `honest-*` agents must score at
least the do-nothing floor, measured, not assumed.

Everything here is *environment*, except the Main, which is the model under
test. Specialists are real LLMs for the same reason as AppWorld's: a
scripted executor would make the multi-agent structure theatre.

This module never imports `are.*` -- the world is duck-typed (see `AreWorld`
in `forge/gaia2/are_world.py`), so the protocol runs under the pinned main
environment for tests and under `.venv-gaia2` for real episodes.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, field

from forge.appworld.partition import Constraints, Topology, Visibility
from forge.appworld.runtime import NO_ANSWER, OUT_OF_STEPS, chat, execution_feedback
from forge.models import require_specialist_parity

#: Both roles default to the same frontier-series model, so parity holds by
#: construction unless a caller explicitly splits them -- and then
#: `require_specialist_parity` decides whether the split is legal.
DEFAULT_MODEL = "gpt-5.6-sol"

#: Version every trajectory records when this contract shaped the policy.
#: Prompt changes alter the experiment; an unversioned change would make old
#: and new rollouts look comparable when they are not.
OBJECTIVE_ACTION_CONTRACT_VERSION = "objective-actions-v1"

#: Semantics shared by the in-process Main, every specialist, and the rendered
#: Harbor instruction. These are deliberately domain-general: the incident
#: that exposed the gap involved a cab's initial BOOKED state, but baking that
#: example into the policy would teach one scenario instead of the principle.
OBJECTIVE_ACTION_CONTRACT = """Objective action contract (literal rules, not suggestions):
- Ground every external write in an explicit user obligation or an observed trigger. A conditional action is not due until its condition is actually observed in a user message, environment notification, or tool result.
- For monitoring, the state observed when an object is created or first inspected is the baseline. An "update" or "change" is a later observed transition away from that baseline, unless the user explicitly says the initial state also counts.
- Complete each requested side effect exactly once successfully for each distinct obligation or observed trigger. Retry only after an explicit failed or rejected call; never repeat a successful write.
- When one write already satisfies overlapping instructions, do not add another write merely to restate the same fact. Keep instructions separate only when the user explicitly requires separate actions, recipients, times, or repetitions.
- Use the transcript as an action ledger before every write: identify the obligation or trigger, verify it is currently due, and verify no successful write has already satisfied it. Never create an extra side effect to cover an ambiguous interpretation."""

#: What the harness returns when the environment announced the episode's end
#: before the Main did. Not a surrender -- the agent did not give up, the
#: world moved on -- but the sweep has to recognise it, exactly like the
#: sentinels in forge/appworld/runtime.py.
ENV_STOP = "(environment stopped)"

#: Answers that commit a turn while telling the user nothing. Gaia2's own
#: reports read "Consultations with Vigdis Rasmussen ... have been scheduled
#: on Friday October 18, 2024"; "completed" cannot match that.
_THIN_REPORTS = frozenset({"completed", "complete", "done", "ok", "finished",
                           "task completed", "all done", ""})

#: Ceiling on one WAIT, in simulated seconds. Waiting jumps the clock, so a
#: large value costs nothing in wall-clock; the cap exists because the first
#: measured episodes showed a Main asking for a full day in one verb --
#: scenario_universe_28_znpabl's horizon is under an hour, and one WAIT 86400
#: leapt past it into ENVIRONMENT_STOP. One hour per verb means a Main that
#: truly needs longer waits again, and anything that arrived in between is
#: delivered before it does.
MAX_WAIT_SECONDS = 900

#: How long the runtime lingers after DONE/FAIL for the next user turn, in
#: simulated seconds. Gaia2 scenarios are multi-turn: the next instruction
#: often fires only after the agent reports back. One hour of simulated
#: time is past every scheduled follow-up in the shipped splits.
TURN_WAIT_SECONDS = 900


@dataclass(frozen=True)
class Msg:
    """One thing the world pushed at the agent between or during steps."""

    kind: str  # "user" | "notification" | "stop"
    text: str = ""


@dataclass
class EpisodeLog:
    """The trajectory, serialized this time.

    AppWorld's `RunLog.interactions` was appended to and never written
    anywhere -- the probe campaigns shipped counters and verdicts while the
    conversations themselves evaporated. Here the chronological `events`
    list *is* the trajectory file (see `as_dict`), and the single-page
    viewer renders it directly. Every event dict carries `type`, `sim_time`,
    and type-specific fields:

        user          content
        notification  content
        main          content                      (the Main's raw line)
        delegation    specialist, brief, report, calls[]
        call          tool, args, result, status   (inside delegation, or
                                                    Main-level in the OPEN control;
                                                    status "malformed" carries the
                                                    raw line instead of tool/args)
        wait          requested, arrived[]
        send_user     content
        done          answer
        surrender     reason
        stop          --

    `malformed` counts every line that drew a protocol correction. It exists
    because the first audited episodes contained delegations whose reports
    claimed "no tool execution was available" over zero recorded calls -- the
    specialist had been emitting unparseable CALL lines and the correction
    loop was invisible, so a model failure could masquerade as a harness one.
    """

    events: list[dict] = field(default_factory=list)
    delegations: int = 0
    specialist_turns: int = 0
    refusals: int = 0  # specialist declined rather than guessed
    #: Calls the world refused at the app boundary. Non-zero means a brief
    #: talked a specialist outside its app -- the Main authored that.
    blocked: int = 0
    blocked_reasons: list[str] = field(default_factory=list)
    waits: int = 0
    user_turns: int = 0
    malformed: int = 0
    #: Zero-call FINALs claiming the tools were down, rejected and retried
    #: once inside the same delegation (the budget never pays for a lie).
    false_outages: int = 0
    #: Gaia2's bN is a soft, adjustable heuristic target. It never prevents a
    #: delegation; these fields expose the economy signal separately from task
    #: correctness.
    delegation_target: int | None = None

    def event(self, world, type_: str, **fields) -> dict:
        e = {"type": type_, "sim_time": world.time_str(), **fields}
        self.events.append(e)
        return e

    def as_dict(self) -> dict:
        economy = delegation_economy_features(
            self.delegation_target, self.delegations)
        return {
            "objective_action_contract": OBJECTIVE_ACTION_CONTRACT_VERSION,
            "events": self.events,
            "delegations": self.delegations,
            "specialist_turns": self.specialist_turns,
            "refusals": self.refusals,
            "blocked": self.blocked,
            "blocked_reasons": self.blocked_reasons,
            "waits": self.waits,
            "user_turns": self.user_turns,
            "malformed": self.malformed,
            "false_outages": self.false_outages,
            **economy,
        }


def delegation_economy_features(
    target: int | None,
    used: int,
    task_success: bool | None = None,
) -> dict:
    """A dense auxiliary economy signal that never changes task feasibility.

    Efficiency is one through the target and decays smoothly as `target/used`
    after it. When terminal task success is known, `reward` is completion-gated
    so doing nothing cannot earn an economy reward. Gaia2's official verdict
    remains the primary reward; this feature is recorded alongside it.
    """
    if used < 0:
        raise ValueError("delegations used cannot be negative")
    if target is None:
        return {
            "delegation_target": None,
            "delegations_over_target": 0,
            "delegation_efficiency": None,
            "delegation_economy_reward": None,
        }
    if target < 1:
        raise ValueError("delegation target must be positive")
    over = max(0, used - target)
    efficiency = 1.0 if used <= target else target / used
    reward = (
        None if task_success is None
        else (efficiency if task_success else 0.0)
    )
    return {
        "delegation_target": target,
        "delegations_over_target": over,
        "delegation_efficiency": round(efficiency, 6),
        "delegation_economy_reward": (
            None if reward is None else round(reward, 6)
        ),
    }


def remaining_seconds(world) -> float:
    """Simulated seconds left before the world stops; inf when it cannot say.

    Every Gaia2 scenario ends after 1000 simulated seconds, and the first
    full campaign spent 73% of its cells discovering that the hard way: a
    Main planning a 3600-second wait killed the world it was working in.
    The world clamps waits itself now; this is how the Main gets to plan
    against the same horizon instead of guessing.
    """
    getter = getattr(world, "remaining", None)
    if getter is None:
        return float("inf")
    try:
        return float(getter())
    except Exception:  # noqa: BLE001 -- a world that cannot say is unbounded
        return float("inf")


def wait_cap(world, requested: int) -> int:
    """The largest wait honouring both our own cap and the world's horizon.

    A world that cannot state a horizon is treated as unbounded, so tests
    and future substrates keep working; a world that can never has its own
    clock run out because of us.
    """
    left = remaining_seconds(world)
    cap = MAX_WAIT_SECONDS if left == float("inf") else min(
        MAX_WAIT_SECONDS, int(left))
    return max(0, min(int(requested), cap))


def _budget_line(world) -> str:
    left = remaining_seconds(world)
    if left == float("inf"):
        return ""
    return (f" You have about {int(left)} simulated seconds left before this "
            "world ends; spend waiting deliberately.")


def _clock_facts(world) -> dict:
    """The world's clock at this instant, when it keeps one.

    Duck-typed like the rest of the world interface: a substrate that
    exposes no clock contributes no fields and the row is still written.
    """
    facts = getattr(world, "clock_facts", None)
    return facts() if callable(facts) else {}


def _deliver(world, log: EpisodeLog, msgs: list[Msg], transcript: list[dict]) -> bool:
    """Append the world's messages to the Main's transcript. True on stop.

    A stop row carries the world's own reason and its clock. Measured
    2026-08-29 across `sweep/gaia2_credit.json` and `sweep/gaia2_v3_credit.json`:
    201 of 249 soft-judged rollouts ended at `ENV_STOP` rather than at an
    answer, and every one of those rows was a bare type-and-timestamp. The
    reason was in hand the whole time -- the stop message reads "Environment
    stopped with state <STATE>" -- and was being dropped here.
    """
    stopped = False
    for m in msgs:
        if m.kind == "stop":
            log.event(world, "stop", reason=m.text, **_clock_facts(world))
            stopped = True
        elif m.kind == "user":
            log.user_turns += 1
            log.event(world, "user", content=m.text)
            transcript.append({"role": "user", "content": f"USER: {m.text}"})
        else:
            log.event(world, "notification", content=m.text)
            transcript.append({"role": "user", "content": f"NOTIFICATION: {m.text}"})
    return stopped


_CALL = re.compile(r"CALL\s+([A-Za-z0-9_]+)\s*(?:::\s*(.*))?$", re.S)

# A FINAL that blames infrastructure -- "the interface is not exposed", "no
# tool execution turn was available" -- from a specialist that has executed
# nothing. The runtime can see both facts, so the claim is checkably false.
#
# The boundary this draws, learned from hand-sorting every zero-call report
# across five campaigns: a fabrication denies the *execution machinery*
# (tool calls, the interface, the turn, the window), usually scoped to this
# run or session; honest inability states a *capability or data* limit
# ("the Cabs tools cannot retrieve your saved home address",
# "InternalContacts provides no lookup tools", "no recipient was provided").
# Honest reports are what the prompt explicitly asks for and must never be
# punished -- the first version's bare `unavailable` branch flagged a
# truthful "delivery confirmation is unavailable" as an outage. The
# subtlest pair: "tools do not expose <a data field>" is a true catalog
# statement; "tools are not exposed" is a lie about the machinery -- which
# is why the denial verbs match only their participle forms.

#: The machinery being denied. Deliberately not bare "interface" or "tools":
#: "the available interface only retrieves the current ride" and "the Cabs
#: tools cannot retrieve X" are honest capability statements.
_OUTAGE_MACHINERY = re.compile(
    r"tool[- ]?(?:calls?|calling|execution|interface|results?)"
    r"|execution (?:interface|turn|window)|interaction window"
    r"|tools\b", re.I)

#: Denial predicates, matched only in a short window AFTER the machinery
#: term, so subject and denial must be about each other. Participle forms
#: only ("not exposed", never "not expose"): the active voice takes a data
#: object and is how honest catalog limits are phrased.
_OUTAGE_DENIAL = re.compile(
    r"unavailable|not (?:available|exposed|accessible|possible|permitted"
    r"|completed)\b"
    r"|did not (?:permit|accept|execute|return)"
    r"|could not be (?:executed|completed|made|issued)"
    r"|were not available|was not available|ended before", re.I)

#: Fabrications that negate the machinery's existence up front: "no
#: tool-call execution opportunity", "no call could be executed", "no
#: callable Messages tool interface". `{0,3}` filler words tolerate an app
#: name in between; the machinery nouns keep "no contacts tool is
#: available" (a true statement from a specialist whose app has no such
#: tool) out. A negated-machinery hit is not enough by itself -- it must be
#: completed by a denial (`_OUTAGE_NEGATED_DENIAL` in the window after it),
#: because "no Messages tool call can target the correct person" is the
#: honest consequence of a missing recipient, not an execution claim.
_OUTAGE_NEGATED = re.compile(
    r"\bno (?:[\w()'’/]+[- ]){0,3}?(?:tool[- ]?(?:calls?|calling|execution"
    r"|results?)|callable|executable)"
    r"|\bno .{0,24}?calls? could\b", re.I)

#: The completion that turns negated machinery into an outage claim: the
#: thing that "was not available / could not be executed / was never
#: provided" about this run. Participles only, as above.
_OUTAGE_NEGATED_DENIAL = re.compile(
    r"available|possible|executed|completed|made\b|issued|provided\b"
    r"|accessible|exposed|permitted|opportunit|turn\b|window", re.I)

#: Verb-complete fabrication shapes that need no second clause.
_OUTAGE_VERBAL = re.compile(
    r"cannot (?:execute|make|run|issue) .{0,24}?(?:tool[- ]?)?calls?"
    r"|not expose[sd]? .{0,32}?tool"
    r"|before any .{0,24}?(?:tool[- ]?)?call", re.I)

#: How far past the machinery term a denial may sit and still be read as
#: denying it.
_OUTAGE_WINDOW = 56


def zero_call_census(events: list[dict]) -> tuple[int, list[str]]:
    """(flagged count, unflagged reports) over a trajectory's delegations.

    The triage feed for the outage corpus. A delegation that executed
    nothing and reported something is either a flagged fabrication (counted
    -- the correction already handled it) or unflagged (listed verbatim, so
    a novel fabrication wording surfaces in the campaign's credit evidence
    for a human to move into fixtures/gaia2/outage_corpus.json). The
    detector's blind spots become a number and a list in every seed's
    evidence file, instead of a review finding three rounds later.
    """
    flagged = 0
    unflagged: list[str] = []
    for event in events:
        if event.get("type") != "delegation":
            continue
        calls = event.get("calls") or []
        executed = [c for c in calls
                    if c.get("status") not in ("malformed", "false-outage")]
        report = str(event.get("report") or "")
        if executed or not report or report == "(no answer within turn limit)":
            continue
        if any(c.get("status") == "false-outage" for c in calls) \
                or _is_false_outage(report):
            flagged += 1
        else:
            unflagged.append(report)
    return flagged, unflagged


def _is_false_outage(report: str) -> bool:
    """Whether a zero-call FINAL claims execution itself was impossible."""
    if _OUTAGE_VERBAL.search(report):
        return True
    negated = _OUTAGE_NEGATED.search(report)
    if negated and _OUTAGE_NEGATED_DENIAL.search(
            report, negated.end(), negated.end() + _OUTAGE_WINDOW):
        return True
    for hit in _OUTAGE_MACHINERY.finditer(report):
        if _OUTAGE_DENIAL.search(report, hit.end(), hit.end() + _OUTAGE_WINDOW):
            return True
    return False


def describe_tool(tool) -> str:
    """One tool, fully described: signature, function description, and every
    argument's own description.

    The argument descriptions are load-bearing, not decoration. The first
    catalog formatter rendered only names and types, so a specialist saw
    `service_type: str` where Gaia2 ships `service_type: type of service
    (Default, Premium, Van)` -- and guessed, errored on 'default', or
    declined outright. The official adapter shows these; so do we.
    """
    params = ", ".join(
        f"{a.name}: {a.arg_type}" + (f" = {a.default!r}" if a.has_default else "")
        for a in tool.args)
    lines = [f"{tool.name}({params})"]
    if tool.function_description:
        lines.append(f"    {str(tool.function_description).strip()}")
    for a in tool.args:
        if a.description:
            lines.append(f"      {a.name}: {str(a.description).strip()}")
    return "\n".join(lines)


def _first_object(raw: str) -> str | None:
    """The first balanced {...} in `raw`, or None if no object closes.

    String-aware: a brace inside a JSON string is data, not structure, so the
    scan tracks quoting and escapes rather than counting characters.
    """
    start = raw.find("{")
    if start < 0:
        return None
    depth, in_string, escaped = 0, False, False
    for i in range(start, len(raw)):
        ch = raw[i]
        if escaped:
            escaped = False
        elif ch == "\\":
            escaped = True
        elif ch == '"':
            in_string = not in_string
        elif not in_string:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return raw[start:i + 1]
    return None


def _parse_call(line: str) -> tuple[str, dict] | str:
    """A (tool, args) pair, or the correction to send back.

    The arguments end where their JSON object closes, not at end-of-line. 96
    of the 108 malformed lines in the v3 campaign were a correct tool name and
    valid JSON with the model's reasoning spilling onto the same line --
    `... :: {"query": "Kare Jensen"} disallowed? No, continue.` -- and every
    one of those corrections burned a turn measuring whether a reasoning model
    can suppress its own commentary, which is none of the abilities under
    test. So: strict parse first, then the first balanced object; a correction
    only when no complete object is there to read (truncated arguments have no
    faithful reading, and guessing would run a tool with arguments the model
    never finished stating).
    """
    m = _CALL.match(line.strip())
    if not m:
        return ("Malformed. Use 'CALL <tool> :: {\"param\": value}' with the "
                "arguments as one JSON object, or 'FINAL: <one line>'.")
    tool, raw = m.group(1), (m.group(2) or "").strip()
    if not raw:
        return tool, {}
    try:
        args = json.loads(raw)
    except json.JSONDecodeError as e:
        blob = _first_object(raw)
        if blob is not None:
            try:
                args = json.loads(blob)
            except json.JSONDecodeError:
                return f"Arguments are not valid JSON ({e}). Send one JSON object."
        else:
            return f"Arguments are not valid JSON ({e}). Send one JSON object."
    if not isinstance(args, dict):
        return "Arguments must be one JSON object, e.g. {\"param\": value}."
    return tool, args


def _specialist_system(world, apps: tuple[str, ...]) -> str:
    """The specialist's entire world, rendered from the same catalogs the
    world itself enforces -- prompt and boundary derive from one source."""
    label = apps[0] if len(apps) == 1 else " + ".join(apps)
    catalogs = "\n\n".join(f"--- {a} ---\n{world.catalog(a)}" for a in apps)
    theirs = f"`{apps[0]}`" if len(apps) == 1 else "the apps you hold"

    return f"""You are the {label} specialist. You are one of several app \
specialists on a team, inside a simulated world with its own clock.

The current simulated date and time is {world.time_str()}. Use THIS date for \
anything time-related -- never a date you believe from outside this world. \
(A specialist once booked a cab for the real-world current date, two years \
after the simulation's; the judge counts that as a wrong write.)

You can use ONLY the tools listed below. You cannot see or use any other app. \
You do NOT know the team's overall task -- only the request your coordinator \
sends you.

{catalogs}

{OBJECTIVE_ACTION_CONTRACT}

If the request needs a fact you have no way to obtain from {theirs}, say so \
plainly instead of guessing. Substituting something that looks similar is worse \
than reporting that you cannot answer.

Execute every part of the request your tools can do RIGHT NOW, then report. \
If part of the request is beyond your tools -- scheduling something for later, \
waiting for or monitoring replies, or anything no listed tool does -- do the \
parts you can and name the part you could not do, and why, in your FINAL line \
so your coordinator can handle it. Your tools are listed above and always \
work; never report your tools as unavailable. (This mirrors the official \
harness's own rule: partial results plus a precise gap beat a refusal.)

Never conclude by reasoning what a tool query would show -- run it. If asked \
whether something exists (replies, entries, events up to now), call the tool \
and report what is actually there, even if you expect it to be empty: "I \
checked and found none" is a real answer, a deduction is not. (Measured: \
specialists told the time deduced "no replies can exist yet" and skipped the \
check; the world had moved without them.)

To act, reply with EXACTLY one line:
    CALL <tool> :: {{"param": value, ...}}
One call per turn. After each call you will see its result and may send \
another. Read a tool's listing before calling it; do not guess parameter names.

If a result says it was truncated, narrow the query -- do not conclude that \
what you did not see does not exist.

When finished, reply with only:
    FINAL: <one line: what you found or did, or why you could not>
"""


def run_specialist(
    client, world, app: str | Iterable[str], brief: str, log: EpisodeLog,
    model: str = DEFAULT_MODEL, max_turns: int = 14,
    calls_out: list[dict] | None = None,
) -> str:
    """Run one specialist against a brief. Returns its one-line report.

    `app` is a single app, or several for the OPEN control. `calls_out`
    collects the per-call records into the enclosing delegation event.
    """
    apps = (app,) if isinstance(app, str) else tuple(app)
    msgs = [
        {"role": "system", "content": _specialist_system(world, apps)},
        # The state-grounding parenthetical is measured medicine, not chrome:
        # this model reasons privately before answering and sometimes imagines
        # its tool calls there, "sees" no results, and reports the tools as
        # down ("no tool calls could be executed in this run"). Stating that
        # nothing has run yet pulled 3 of 4 probe samples back to acting on a
        # brief that refused 4 of 4 without it.
        {"role": "user", "content":
            f"Coordinator's request:\n{brief}\n\n(You have made no tool calls "
            "yet. The interface is live and waiting for your first CALL line; "
            "results will appear as Output after each call.)"},
    ]
    executed = 0
    outage_corrected = False
    for _ in range(max_turns):
        out = chat(client, msgs, model=model).strip()
        msgs.append({"role": "assistant", "content": out})
        if out.startswith("FINAL:"):
            report = out[len("FINAL:"):].strip()
            # A zero-call specialist reporting its tools as down is stating
            # something the runtime can see is false (this model reasons
            # privately and sometimes imagines calls that never ran). Reject
            # it once, inside the same delegation -- the Main's budget never
            # pays for a fabricated outage -- then accept whatever follows.
            if executed == 0 and not outage_corrected and _is_false_outage(report):
                outage_corrected = True
                log.false_outages += 1
                if calls_out is not None:
                    calls_out.append({"tool": None, "args": None,
                                      "status": "false-outage",
                                      "raw": report[:400]})
                msgs.append({"role": "user", "content":
                    "Reality check: you have made zero tool calls in this "
                    "conversation and your tools are operational, so that "
                    "report is false. Make your first CALL now, or give a "
                    "FINAL stating the real reason you cannot."})
                continue
            if re.search(r"\bcannot\b|\bcould not\b|\bcouldn['’]t\b|\bunable\b"
                         r"|\bno way\b|\bdon['’]t have\b|\bwas(?: not|n['’]t) able\b"
                         r"|\bunavailable\b", report, re.I):
                log.refusals += 1
            return report

        parsed = _parse_call(out)
        if isinstance(parsed, str):
            # Recorded, not just corrected: an unparseable line left no trace
            # once, and its delegation read like a harness outage.
            log.malformed += 1
            if calls_out is not None:
                calls_out.append({"tool": None, "args": None,
                                  "status": "malformed", "raw": out[:400]})
            msgs.append({"role": "user", "content": parsed})
            continue
        tool, args = parsed
        text, status = world.call(apps, tool, args)
        record = {"tool": tool, "args": args, "status": status,
                  "result": execution_feedback(text)}
        if calls_out is not None:
            calls_out.append(record)
        if status == "refused":
            # The app boundary is the world's, not the prompt's. Counted and
            # named because the Main's brief caused it.
            log.blocked += 1
            log.blocked_reasons.append(f"{tool}: {text}")
            msgs.append({"role": "user", "content": f"Output:\nRefused: {text}"})
            continue
        log.specialist_turns += 1
        executed += 1
        msgs.append({"role": "user", "content": f"Output:\n{execution_feedback(text)}"})
    return NO_ANSWER


#: The turn-commit contract. Gaia2 counts turns by the agent's messages to
#: the user: when the Nth lands, the judge validates turn N and calls
#: env.stop() if it does not match. Measured 2026-07-30 over the v2 campaign:
#: 88 of 108 fatally stopped cells had committed a turn first, so casual
#: progress updates were killing episodes outright.
TURN_RULE = """
HOW REPORTING TO THE USER WORKS -- read this twice, it decides most episodes.
Every message you send the user (USER :: and DONE ::) COMMITS the work you \
have done so far for review and advances this world to its next phase. It is \
not chat. Measured consequence: 88 of 108 killed episodes died immediately \
after a message to the user, because the work committed did not yet match \
what was asked.

So:
- NEVER send progress updates, acknowledgements, or "I have started" notes. A \
  premature report ends the episode with the task unfinished.
- Send a report only when everything the user's current request asked for is \
  actually DONE -- every message sent, every booking made, every event created.
- Make the report substantive: NAME every person, item, event and time you \
  acted on -- "Consultations with Vigdis Rasmussen, Birgitta Kjaer and Astrid \
  Jensen have been scheduled on Friday October 18, 2024", never "scheduled the \
  consultations as requested". Your report is compared against a reference \
  report of the same work, so a summary that omits the names does not match, \
  and a bare one-word confirmation is not a report at all.
- After you report, the world may move: replies, confirmations, or a new \
  request can arrive. If they do, keep working -- the episode is not over \
  until you are told it is or nothing more arrives.
"""


def _main_system(world, constraints: Constraints, catalogs: dict[str, str] | None) -> str:
    open_control = constraints.main_has_apis

    if open_control:
        acting = """To act, reply with EXACTLY one line, using one of these verbs:
    CALL <tool> :: {"param": value, ...}     run one tool yourself"""
        roster_note = "You hold every tool yourself. The catalogs are listed below."
    else:
        if constraints.topology is Topology.CHAIN:
            routing = (f"You may delegate ONLY to {constraints.roster[0]}. Specialists "
                       "hand off down the chain themselves: "
                       + " -> ".join(constraints.roster))
        else:
            routing = "You may delegate to: " + ", ".join(constraints.roster)
        acting = """To act, reply with EXACTLY one line, using one of these verbs:
    DELEGATE <specialist> :: <your request in plain English>"""
        roster_note = routing + "\n" + (
            "You know only their names, not what they can do. Ask them if you need to know."
            if constraints.visibility is Visibility.NAMES
            else "Their capabilities are listed below."
        )

    listing = ""
    if catalogs:
        listing = "\n\nAPI catalogs:\n\n" + "\n\n".join(
            f"--- {app} ---\n{cat}" for app, cat in catalogs.items())

    budget = (
        "Delegation efficiency is not measured in this configuration."
        if constraints.delegation_budget is None or open_control
        else (
            f"Your soft delegation target is {constraints.delegation_budget}. "
            "Plan economically, but this is NOT a hard cap: continue delegating "
            "when needed to complete the task. Going over lowers only the "
            "auxiliary economy signal."
        )
    )

    body = "" if open_control else """
Each specialist can use ONLY its own app and does NOT know your task.

Rules that decide whether you succeed:
- A specialist cannot see other apps. If a request needs a fact that lives in a \
different app, YOU must obtain that fact first and put it in the request.
- Some specialists cannot possibly know some things. Ask the one that can.
- Be specific. A vague request produces vague work.
- Specialists act immediately and singly: they cannot wait, monitor, or \
schedule anything for later -- the clock is YOURS (WAIT). Ask for one \
specific action at a time, say exactly what output you need, and handle \
timing yourself.
- Delegating costs time: each request/report round-trip consumes roughly \
30-60 seconds of world time while you both work. Budget for it. When a \
deadline is near, act on what you already know -- re-verifying a silence \
you have already observed spends the deadline to learn nothing. (Measured: \
episodes ordered a correct cab a minute late, after exactly one redundant \
recheck of an already-observed three-minute silence.)
"""

    return f"""You are the Main coordinator for a user's request, acting inside \
a simulated world with a clock. The current simulated time is \
{world.time_str()}.{_budget_line(world)}

{roster_note}{listing}
{budget}
{OBJECTIVE_ACTION_CONTRACT}
{TURN_RULE}
{acting}
    WAIT <seconds>                           let simulated time pass until the \
next notification or the timeout
    USER :: <message>                        send the user a message
    DONE :: <one line the user will read: what you did or found, with \
names, times, and identifiers>
    FAIL :: <one-line reason>
{body}
Events in this world happen on the clock: replies, confirmations and follow-ups \
arrive at later simulated times. When you are blocked on something that has not \
happened yet, WAIT for it -- new notifications and user messages are delivered \
to you as they arrive.

DONE sends your answer to the user and ends your turn; if the user follows up, \
you continue. If you cannot complete the task, reply FAIL -- it tells the user \
the truth and stops. Never claim completion you did not achieve, and never put \
a failure report in DONE -- FAIL is the channel for it.
"""


def run_main(
    client, world, task: str, constraints: Constraints, log: EpisodeLog,
    model: str = DEFAULT_MODEL, sub_model: str | None = None,
    max_steps: int = 40, max_turns: int = 4,
    allow_sub_downgrade: bool = False,
) -> str:
    """Run the Main. Returns the final turn's answer string.

    `max_steps` bounds LLM steps across the whole episode; `max_turns`
    bounds user turns, mirroring the official harness's `max_turns`.
    `allow_sub_downgrade` is the explicit escape hatch in the parity rule.
    """
    require_specialist_parity(model, sub_model or model,
                              allow_downgrade=allow_sub_downgrade)
    log.delegation_target = (
        None if constraints.main_has_apis else constraints.delegation_budget
    )

    open_control = constraints.main_has_apis
    catalogs = (
        {app: world.catalog(app) for app in constraints.roster}
        if (open_control or constraints.visibility is Visibility.DOCS)
        else None
    )
    msgs: list[dict] = [
        {"role": "system", "content": _main_system(world, constraints, catalogs)},
        {"role": "user", "content": f"USER: {task}"},
    ]
    log.event(world, "user", content=task)
    log.user_turns += 1
    answer: str | None = None  # the current turn's outcome, returned at the end
    thin_report_corrected = False

    for _ in range(max_steps):
        if _deliver(world, log, world.drain(), msgs):
            return answer if answer is not None else ENV_STOP

        out = chat(client, msgs, model=model).strip()
        msgs.append({"role": "assistant", "content": out})
        log.event(world, "main", content=out)

        if out.startswith("FAIL"):
            reason = out.split("::", 1)[1].strip() if "::" in out else ""
            answer = f"FAIL :: {reason or 'no reason given'}"
            world.send_user(f"I could not complete this task: {reason or 'no reason given'}")
            log.event(world, "surrender", reason=reason)
        elif out.startswith("DONE"):
            answer = out.split("::", 1)[1].strip() if "::" in out else "completed"
            # The DONE text IS the message the user receives, and the oracle's
            # own report carries specifics. A bare token commits the turn with
            # an empty report, which the judge cannot match.
            if (not thin_report_corrected
                    and answer.strip().lower().rstrip(".") in _THIN_REPORTS):
                thin_report_corrected = True
                log.malformed += 1
                msgs.append({"role": "user", "content":
                    "That DONE text is what the user will read, and it says "
                    "nothing. Reply DONE again with a substantive report of "
                    "what you actually did -- names, times, identifiers -- or "
                    "keep working if the task is not finished."})
                continue
            world.send_user(answer)
            log.event(world, "done", answer=answer)
        elif out.startswith("WAIT"):
            m = re.match(r"WAIT\s+(\d+)", out)
            if not m:
                log.malformed += 1
                msgs.append({"role": "user", "content":
                             "Malformed. Use 'WAIT <seconds>' with a whole number."})
                continue
            seconds = wait_cap(world, m.group(1))
            log.waits += 1
            arrived = world.wait(seconds)
            log.event(world, "wait", requested=seconds,
                      arrived=[m_.text for m_ in arrived if m_.kind != "stop"])
            if _deliver(world, log, arrived, msgs):
                return answer if answer is not None else ENV_STOP
            if not arrived:
                msgs.append({"role": "user", "content":
                             f"You waited {seconds} seconds. No notification "
                             f"arrived. The simulated time is now "
                             f"{world.time_str()}.{_budget_line(world)}"})
            continue
        elif out.startswith("USER"):
            text = out.split("::", 1)[1].strip() if "::" in out else ""
            if not text:
                log.malformed += 1
                msgs.append({"role": "user", "content":
                             "Malformed. Use 'USER :: <message>'."})
                continue
            world.send_user(text)
            log.event(world, "send_user", content=text)
            msgs.append({"role": "user", "content": "Message sent to the user."})
            continue
        elif open_control and out.startswith("CALL"):
            parsed = _parse_call(out)
            if isinstance(parsed, str):
                log.malformed += 1
                log.event(world, "call", tool=None, args=None,
                          status="malformed", raw=out[:400])
                msgs.append({"role": "user", "content": parsed})
                continue
            tool, args = parsed
            text, status = world.call(constraints.roster, tool, args)
            log.event(world, "call", tool=tool, args=args, status=status,
                      result=execution_feedback(text))
            if status == "refused":
                log.blocked += 1
                log.blocked_reasons.append(f"{tool}: {text}")
                msgs.append({"role": "user", "content": f"Output:\nRefused: {text}"})
            else:
                log.specialist_turns += 1
                msgs.append({"role": "user",
                             "content": f"Output:\n{execution_feedback(text)}"})
            continue
        elif out.startswith("DELEGATE"):
            if open_control:
                msgs.append({"role": "user", "content":
                             "You have no specialists. Use CALL to act yourself."})
                continue
            m = re.match(r"DELEGATE\s+(\w+)\s*::\s*(.+)", out, re.S)
            if not m:
                log.malformed += 1
                msgs.append({"role": "user", "content":
                             "Malformed. Use 'DELEGATE <name> :: <request>'."})
                continue
            who, brief = m.group(1), m.group(2).strip()
            allowed = constraints.allowed_targets("main")
            if who not in allowed:
                # The topology is enforced here, not requested politely.
                msgs.append({"role": "user", "content":
                             f"You cannot reach {who}. You may delegate to: {list(allowed)}"})
                continue
            log.delegations += 1
            calls: list[dict] = []
            reply = run_specialist(client, world, who, brief, log,
                                   model=sub_model or model, calls_out=calls)
            log.event(world, "delegation", specialist=who, brief=brief,
                      report=reply, calls=calls)
            economy = delegation_economy_features(
                log.delegation_target, log.delegations)
            usage = ""
            if log.delegation_target is not None:
                usage = (
                    f"\nDelegations used: {log.delegations}; soft target: "
                    f"{log.delegation_target}; over target: "
                    f"{economy['delegations_over_target']}. The target does "
                    "not block further work."
                )
            msgs.append({"role": "user",
                         "content": f"{who} reports: {reply}{usage}"})
            continue
        else:
            log.malformed += 1
            verbs = "CALL, WAIT, USER, DONE, FAIL" if open_control else \
                    "DELEGATE, WAIT, USER, DONE, FAIL"
            msgs.append({"role": "user", "content":
                         f"Malformed. Reply with exactly one line using one of: {verbs}."})
            continue

        # Only DONE and FAIL reach here: the turn is over. Linger for the next
        # user turn -- Gaia2 scenarios frequently schedule the follow-up to
        # fire only after the agent reports back.
        if log.user_turns >= max_turns:
            return answer
        linger = wait_cap(world, TURN_WAIT_SECONDS)
        arrived = world.wait(linger)
        log.event(world, "wait", requested=linger,
                  arrived=[m_.text for m_ in arrived if m_.kind != "stop"])
        if _deliver(world, log, arrived, msgs):
            return answer
        # A notification counts as much as a user message: the world often
        # answers a completed phase with a reply or confirmation, and the
        # next phase of work hangs off it.
        if not any(m_.kind in ("user", "notification") for m_ in arrived):
            return answer

    return answer if answer is not None else OUT_OF_STEPS
