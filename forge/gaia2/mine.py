"""Mine Gaia2 scenarios: rosters and information seams, without parsing code.

Gaia2 (Meta ARE) is the second substrate this forge admits. Its ground truth
is not reference *code* but a list of OracleEvents -- gold write actions, each
naming an app, a function and literal argument values -- plus the complete
initial state of every app. Two consequences for mining:

  * **roster** -- AppWorld's came from `apis.<app>.<method>(` in solution
    code. Here it is the set of apps the gold writes touch, **plus** every
    app an information seam proves was read. Reads never appear in oracle
    events (Gaia2 verifies writes only), so seam sources are the only
    evidence that an app's state was needed.

  * **seams** -- AppWorld ran a taint pass over solution code
    (`forge/appworld/seams.py`). Here a seam is **state provenance**: a gold
    write whose argument value exists in a *different* app's initial state,
    is absent from the target app's own state, and does not appear in the
    user instruction. Such a value had to be read in one app and carried
    into another -- the fact crossed, so a partition forces it through a
    conversation.

**This is a heuristic, not a proof**, exactly as `seams.py` is: exact string
match under-reports (a date reformatted in transit is invisible) and ambient
strings could over-report, which is why values shorter than
`MIN_VALUE_LEN` are ignored and values present in more than
`MAX_SEAM_SOURCES` other apps are treated as ambient rather than as facts.
Every reported seam still names the two apps, the function and the argument,
so a human can check any row of the admission sweep by hand.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

#: Apps that are never a coordination role. AgentUserInterface is the user
#: channel -- every scenario touches it, exactly like AppWorld's `supervisor`,
#: and counting it would fake a collaborator into every roster. SystemApp is
#: environment internals.
_INFRA_APPS = frozenset({"AgentUserInterface", "SystemApp"})

#: Below this length a string is too generic to be provenance ("true",
#: "INBOX", short names): matching it across app states would manufacture
#: seams out of coincidence.
MIN_VALUE_LEN = 8

#: A value found in more than this many other apps is ambient state (a city
#: name, a timezone), not a fact that crossed from one app to another.
MAX_SEAM_SOURCES = 2

MIN_ROSTER = 2  # below this there is no coordination to test


@dataclass(frozen=True)
class GoldWrite:
    """One oracle write action: the app it mutates and its literal args."""

    app: str
    function: str
    args: tuple[tuple[str, str], ...]  # (name, value) -- string-valued args only


@dataclass(frozen=True)
class Seam:
    """A fact read in `source` that a gold write carries into `target`."""

    source: str
    target: str
    value: str
    function: str
    arg: str


@dataclass(frozen=True)
class Gaia2Span:
    """What a scenario requires, measured from its gold writes and state."""

    scenario_id: str
    roster: tuple[str, ...]
    write_apps: tuple[str, ...]
    seams: tuple[Seam, ...]

    @property
    def usable(self) -> bool:
        return len(self.roster) >= MIN_ROSTER

    @property
    def seamful(self) -> bool:
        return bool(self.seams)


def _events(scenario: dict) -> list[dict]:
    return scenario.get("events") or []


def gold_writes(scenario: dict) -> list[GoldWrite]:
    """Every OracleEvent write, in event order. Infra apps are not writes."""
    out = []
    for event in _events(scenario):
        if event.get("class_name") != "OracleEvent":
            continue
        action = event.get("action") or {}
        app = action.get("app")
        if not app or app in _INFRA_APPS:
            continue
        args = tuple(
            (arg.get("name", ""), arg["value"])
            for arg in action.get("args") or []
            if isinstance(arg.get("value"), str)
        )
        out.append(GoldWrite(app=app, function=action.get("function", ""), args=args))
    return out


def user_text(scenario: dict) -> str:
    """Everything the user said to the agent. A value in here was handed
    over, not discovered, so it can never witness a seam."""
    chunks = []
    for event in _events(scenario):
        if event.get("event_type") != "USER":
            continue
        for arg in (event.get("action") or {}).get("args") or []:
            if isinstance(arg.get("value"), str):
                chunks.append(arg["value"])
    return "\n".join(chunks)


def _string_leaves(node: object) -> Iterator[str]:
    """Every string in a nested state blob -- keys included, because Gaia2
    keeps entity ids as dict keys as often as values."""
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(key, str):
                yield key
            yield from _string_leaves(value)
    elif isinstance(node, (list, tuple)):
        for item in node:
            yield from _string_leaves(item)
    elif isinstance(node, str):
        yield node


def app_state_values(scenario: dict) -> dict[str, frozenset[str]]:
    """Provenance-eligible strings per app, from each app's initial state."""
    out = {}
    for app in scenario.get("apps") or []:
        name = app.get("name")
        if not name or name in _INFRA_APPS:
            continue
        out[name] = frozenset(
            value
            for value in _string_leaves(app.get("app_state"))
            if len(value) >= MIN_VALUE_LEN
        )
    return out


def information_seams(scenario: dict) -> list[Seam]:
    """Every fact the gold writes prove crossed between apps.

    One seam per (source, target) pair, mirroring `seams.py`: the same pair
    crossing five values is one partition-relevant edge, not five.
    """
    states = app_state_values(scenario)
    instruction = user_text(scenario)
    seams: list[Seam] = []
    seen: set[tuple[str, str]] = set()
    for write in gold_writes(scenario):
        local = states.get(write.app, frozenset())
        for arg_name, value in write.args:
            if len(value) < MIN_VALUE_LEN:
                continue
            if value in instruction:
                continue  # handed over in the brief from the user
            if value in local:
                continue  # discoverable inside the target app itself
            sources = sorted(
                app
                for app, values in states.items()
                if app != write.app and value in values
            )
            if not sources or len(sources) > MAX_SEAM_SOURCES:
                continue  # unknown origin, or ambient
            for source in sources:
                if (source, write.app) in seen:
                    continue
                seen.add((source, write.app))
                seams.append(
                    Seam(
                        source=source,
                        target=write.app,
                        value=value,
                        function=write.function,
                        arg=arg_name,
                    )
                )
    return seams


def derive_roster(scenario: dict) -> tuple[str, ...]:
    """Apps the gold writes touch, plus apps a seam proves were read."""
    apps = {write.app for write in gold_writes(scenario)}
    apps |= {seam.source for seam in information_seams(scenario)}
    return tuple(sorted(apps))


def scenario_id(scenario: dict) -> str:
    return (
        (scenario.get("metadata") or {}).get("definition", {}).get("scenario_id", "")
    )


def admit(scenario: dict) -> Gaia2Span:
    """Measure one scenario. `usable` and `seamful` are read off the result."""
    seams = tuple(information_seams(scenario))
    return Gaia2Span(
        scenario_id=scenario_id(scenario),
        roster=derive_roster(scenario),
        write_apps=tuple(sorted({w.app for w in gold_writes(scenario)})),
        seams=seams,
    )
