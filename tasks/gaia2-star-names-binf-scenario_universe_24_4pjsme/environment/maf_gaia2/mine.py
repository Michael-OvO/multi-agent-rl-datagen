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
from functools import lru_cache

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

#: Containment matching (a state leaf appearing *inside* a gold argument)
#: needs a stricter floor than equality: below this, containment is
#: coincidence -- short tokens, dates, and first names recur across apps.
#: At or above it, a leaf inside an argument is the fact itself, carried
#: whole: a filename inside a serialized attachment list, a job title
#: inside a composed email body.
CONTAINMENT_MIN_LEN = 12


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
class BlindFact:
    """A fact a gold write consumes that no roster seat can read.

    The leaf provably exists in the world -- inside `sources`' initial
    state -- and provably reaches the gold argument, but every app that
    holds it is outside the roster. Under this partition the scenario is
    unsolvable by construction, and every episode run on it is money spent
    measuring nothing. v4 paid for four of them on one scenario before
    this existed.
    """

    app: str
    function: str
    arg: str
    leaf: str
    sources: tuple[str, ...]


@dataclass(frozen=True)
class Gaia2Span:
    """What a scenario requires, measured from its gold writes and state."""

    scenario_id: str
    roster: tuple[str, ...]
    write_apps: tuple[str, ...]
    seams: tuple[Seam, ...]
    #: Environment events (a reply arriving, a confirmation) whose
    #: dependencies name an oracle event: the world reacts only after the
    #: judge's turn condition matches the agent's actions against the oracle.
    #: Measured because the first audited episodes hit it blind -- with the
    #: scripted judge (no LLM soft-checkers) a paraphrased email never
    #: matches, the reply never schedules, and the scenario's later phases
    #: are unreachable no matter what the agent does.
    conditioned_env_events: int = 0
    #: A task-specific *heuristic target* for delegation economy. It is not a
    #: solvability claim and never blocks execution. The estimate minimizes
    #: same-app visits within causal phases, separates visits across waits and
    #: environment/user barriers, and chooses one source when a seam fact is
    #: available from alternative apps. See delegation_heuristic().
    delegation_target: int = 0
    #: Facts the gold writes consume that only off-roster apps hold. Any
    #: entry means the partition is incomplete and the scenario cannot be
    #: solved from its own seats -- see BlindFact.
    roster_blind: tuple[BlindFact, ...] = ()

    @property
    def usable(self) -> bool:
        return len(self.roster) >= MIN_ROSTER

    @property
    def partition_complete(self) -> bool:
        """Whether every consumed fact is reachable from some seat."""
        return not self.roster_blind

    @property
    def seamful(self) -> bool:
        return bool(self.seams)

    @property
    def reply_conditioned(self) -> bool:
        """Whether later phases unlock only by matching the oracle -- which
        couples episode *dynamics*, not just the verdict, to judge strictness."""
        return self.conditioned_env_events > 0


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


def _provenance_requirements(
    scenario: dict,
) -> list[tuple[tuple[str, str, str, str], tuple[str, ...]]]:
    """Consumed facts and every plausible source app for each one.

    Unlike the public seam list, this retains every fact. The seam list
    deliberately collapses repeated source/target pairs because it describes
    the partition graph; delegation pricing needs the uncollapsed facts so
    different requirements with different alternative sources are not lost.
    """
    states = app_state_values(scenario)
    instruction = user_text(scenario)
    requirements = []
    for write in gold_writes(scenario):
        local = states.get(write.app, frozenset())
        for arg_name, value in write.args:
            if len(value) < MIN_VALUE_LEN or value in instruction or value in local:
                continue
            sources = tuple(
                sorted(
                    app
                    for app, values in states.items()
                    if app != write.app and value in values
                )
            )
            if not sources or len(sources) > MAX_SEAM_SOURCES:
                continue
            key = (write.app, write.function, arg_name, value)
            requirements.append((key, sources))
    return requirements


def information_seams(scenario: dict) -> list[Seam]:
    """Every fact the gold writes prove crossed between apps.

    One seam per (source, target) pair, mirroring `seams.py`: the same pair
    crossing five values is one partition-relevant edge, not five.
    """
    seams: list[Seam] = []
    seen: set[tuple[str, str]] = set()
    for (target, function, arg, value), sources in _provenance_requirements(
        scenario
    ):
        for source in sources:
            if (source, target) in seen:
                continue
            seen.add((source, target))
            seams.append(
                Seam(
                    source=source,
                    target=target,
                    value=value,
                    function=function,
                    arg=arg,
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


def conditioned_env_events(scenario: dict) -> int:
    """Environment events gated on the agent matching the oracle.

    An ENV event whose `dependencies` include an OracleEvent id fires only
    after the judge validates the corresponding turn. Zero means the
    scenario's schedule is unconditional and any judge configuration sees
    the same world; non-zero means the deterministic scripted judge can
    freeze the world mid-scenario (see Gaia2Span.reply_conditioned).
    """
    oracle_ids = {
        event.get("event_id")
        for event in _events(scenario)
        if event.get("class_name") == "OracleEvent"
    }
    return sum(
        1
        for event in _events(scenario)
        if event.get("event_type") == "ENV"
        and any(dep in oracle_ids for dep in event.get("dependencies") or [])
    )


@dataclass(frozen=True)
class DelegationHeuristic:
    """Auditable components of the soft delegation target.

    `write_visits` is the minimum number of same-app runs in the oracle DAG
    after external barriers split it into causal phases. `read_visits` is the
    least additional set of source apps needed for the state-provenance seams.
    The sum is a useful economy target, not proof that a task is impossible
    below it or guaranteed solvable at it: Gaia2 has no reference read trace,
    and exact-string provenance deliberately under-reports transformed facts.
    """

    target: int
    write_visits: int
    read_visits: int
    phases: int


def _oracle_action_events(scenario: dict) -> list[dict]:
    """Oracle writes performed by specialists, retaining their DAG metadata."""
    return [
        event
        for event in _events(scenario)
        if event.get("class_name") == "OracleEvent"
        and (event.get("action") or {}).get("app") not in _INFRA_APPS
    ]


def _event_phases(scenario: dict) -> dict[str, int]:
    """Assign every event a causal phase.

    USER/ENV events and infrastructure oracle actions hand control back to the
    Main, so a specialist delegation cannot span them. A non-infrastructure
    oracle action with more than the normal one-second relative delay likewise
    requires the Main to wait. Dependency depth through those barriers, rather
    than JSON list order, is the phase: independent writes at the same frontier
    can therefore be regrouped by app, while a same-app return after a reply or
    wait is charged as a new visit.
    """
    by_id = {
        event.get("event_id"): event
        for event in _events(scenario)
        if event.get("event_id")
    }
    visiting: set[str] = set()

    @lru_cache(maxsize=None)
    def phase(event_id: str) -> int:
        if event_id in visiting:
            raise ValueError(f"cycle in Gaia2 event dependencies at {event_id!r}")
        event = by_id[event_id]
        visiting.add(event_id)
        try:
            parent_phase = max(
                (phase(dep) for dep in event.get("dependencies") or [] if dep in by_id),
                default=0,
            )
        finally:
            visiting.remove(event_id)

        action_app = (event.get("action") or {}).get("app")
        external_barrier = (
            event.get("event_type") in {"USER", "ENV"}
            or (
                event.get("class_name") == "OracleEvent"
                and action_app in _INFRA_APPS
            )
        )
        try:
            relative = float(event.get("event_relative_time") or 0)
        except (TypeError, ValueError):
            relative = 0
        delayed_action = (
            event.get("class_name") == "OracleEvent"
            and action_app not in _INFRA_APPS
            and relative > 1.0
        )
        return parent_phase + int(external_barrier or delayed_action)

    return {event_id: phase(event_id) for event_id in by_id}


def _oracle_ancestors(
    event_id: str, by_id: dict[str, dict], oracle_ids: frozenset[str]
) -> frozenset[str]:
    """Transitive specialist-oracle predecessors of one event."""

    @lru_cache(maxsize=None)
    def visit(current: str) -> frozenset[str]:
        found: set[str] = set()
        event = by_id.get(current) or {}
        for dep in event.get("dependencies") or []:
            if dep in oracle_ids:
                found.add(dep)
            if dep in by_id:
                found.update(visit(dep))
        return frozenset(found)

    return visit(event_id)


def _minimum_app_runs(events: list[dict], by_id: dict[str, dict]) -> int:
    """Minimum label runs over topological orders of one causal phase."""
    if not events:
        return 0
    ids = [event["event_id"] for event in events]
    index = {event_id: i for i, event_id in enumerate(ids)}
    oracle_ids = frozenset(
        event_id
        for event_id, event in by_id.items()
        if event.get("class_name") == "OracleEvent"
        and (event.get("action") or {}).get("app") not in _INFRA_APPS
    )
    predecessors = []
    for event_id in ids:
        mask = 0
        for ancestor in _oracle_ancestors(event_id, by_id, oracle_ids):
            if ancestor in index:
                mask |= 1 << index[ancestor]
        predecessors.append(mask)
    apps = [(event.get("action") or {}).get("app", "") for event in events]
    full = (1 << len(events)) - 1

    @lru_cache(maxsize=None)
    def solve(done: int, last_app: str) -> int:
        if done == full:
            return 0
        best = len(events) + 1
        for i, app in enumerate(apps):
            bit = 1 << i
            if done & bit or predecessors[i] & ~done:
                continue
            best = min(
                best,
                int(app != last_app) + solve(done | bit, app),
            )
        if best > len(events):
            raise ValueError("cycle in Gaia2 oracle dependencies")
        return best

    return solve(0, "")


def _minimum_paid_sources(candidate_sets: list[frozenset[str]]) -> int:
    """Minimum distinct apps covering provenance requirements.

    A source read can return all initially stored facts from that app, so one
    paid visit covers every remaining requirement that names the source.
    """
    requirements = tuple(c for c in candidate_sets if c)

    @lru_cache(maxsize=None)
    def cover(remaining: tuple[frozenset[str], ...]) -> int:
        if not remaining:
            return 0
        requirement = min(remaining, key=len)
        return min(
            1
            + cover(tuple(r for r in remaining if source not in r))
            for source in requirement
        )

    return cover(requirements)


def delegation_heuristic(scenario: dict) -> DelegationHeuristic:
    """Estimate a useful, non-blocking delegation target from causal structure.

    The old estimate run-length-compressed the JSON event order. That both
    overcounted independent interleavings (`Calendar, Emails, Calendar` at the
    same frontier) and undercounted adjacent same-app actions separated by a
    reply or wait. This estimate operates on dependency phases instead.

    State provenance is also choice-aware: if Contacts *or* InternalContacts
    can supply the same fact, only one source visit is charged. Existing source
    app visits at or before the consuming phase can carry the read for free.
    """
    action_events = _oracle_action_events(scenario)
    if not action_events:
        return DelegationHeuristic(0, 0, 0, 0)

    by_id = {
        event.get("event_id"): event
        for event in _events(scenario)
        if event.get("event_id")
    }
    phases = _event_phases(scenario)
    grouped: dict[int, list[dict]] = {}
    for event in action_events:
        grouped.setdefault(phases.get(event["event_id"], 0), []).append(event)
    action_ids = frozenset(event["event_id"] for event in action_events)
    write_visits = sum(
        _minimum_app_runs(events, by_id)
        for _, events in sorted(grouped.items())
    )

    # Group alternative provenance sources for the same consumed fact.
    requirements: dict[tuple[str, str, str, str], set[str]] = {}
    for key, sources in _provenance_requirements(scenario):
        requirements.setdefault(key, set()).update(sources)

    paid: list[frozenset[str]] = []
    for (target, function, arg, value), sources in requirements.items():
        consumers = [
            event
            for event in action_events
            if (event.get("action") or {}).get("app") == target
            and (event.get("action") or {}).get("function") == function
            and any(
                item.get("name") == arg and item.get("value") == value
                for item in (event.get("action") or {}).get("args") or []
            )
        ]

        def source_visit_can_precede_consumers(
            source: str, required_consumers: list[dict]
        ) -> bool:
            for source_event in action_events:
                if (source_event.get("action") or {}).get("app") != source:
                    continue
                source_id = source_event["event_id"]
                source_phase = phases.get(source_id, 0)
                ancestors = _oracle_ancestors(
                    source_id, by_id, action_ids
                )
                if all(
                    source_phase < phases.get(consumer["event_id"], 0)
                    or (
                        source_phase == phases.get(consumer["event_id"], 0)
                        and consumer["event_id"] not in ancestors
                    )
                    for consumer in required_consumers
                ):
                    return True
            return False

        free = any(
            source_visit_can_precede_consumers(source, consumers)
            for source in sources
        )
        if not free:
            paid.append(frozenset(sources))

    read_visits = _minimum_paid_sources(paid)
    return DelegationHeuristic(
        target=write_visits + read_visits,
        write_visits=write_visits,
        read_visits=read_visits,
        phases=len(grouped),
    )


def delegation_target(scenario: dict) -> int:
    """The adjustable economy target's task-derived default."""
    return delegation_heuristic(scenario).target


def _given_text(scenario: dict) -> str:
    """Everything the world hands the agent: the instruction, plus the
    content of every non-oracle event (notifications, delivered messages,
    scheduled replies). A fact that arrives through any of these channels
    is given, not blind -- scenario_universe_22_6wkrhc's chat partner is
    named only in the off-roster Chats state, but an environment event
    delivers a message bearing the name, so the scenario is solvable.

    Oracle events are excluded: their args are the answer key, and counting
    them as given would mark every scenario solvable by definition.
    """
    parts = [user_text(scenario)]
    for event in _events(scenario):
        if event.get("class_name") == "OracleEvent":
            continue
        for arg in (event.get("action") or {}).get("args") or []:
            value = arg.get("value")
            if isinstance(value, str):
                parts.append(value)
    return "\n".join(parts)


def roster_blind_facts(scenario: dict) -> tuple[BlindFact, ...]:
    """Facts consumed by gold writes that only off-roster apps can supply.

    The seam pass compares argument values against state leaves by equality.
    That misses containment: scenario_universe_24_tg3h3h's gold emails carry
    attachment_paths='["/Documents/wiki/wikipedia_41.txt"]', and the Files
    app's leaves are `wikipedia_41.txt` and `demo_filesystem/Documents/wiki/
    wikipedia_41.txt` -- provably the source, never equal to the serialized
    list. Files stayed off the roster and all four v4 arms burned their whole
    budget searching mailboxes for a file no seat could reach.

    This pass asks the narrower admission question: is there a leaf that
    (a) appears inside a gold argument whole (equality, or containment at
    CONTAINMENT_MIN_LEN or longer), (b) is never handed to the agent --
    not in the instruction, not in anything a non-oracle event delivers
    mid-episode -- and (c) exists only in apps outside the roster? The
    ambient guard mirrors the seam rule: a leaf held by more than
    MAX_SEAM_SOURCES apps is scenery, not provenance.
    """
    states = app_state_values(scenario)
    given = _given_text(scenario)
    roster = set(derive_roster(scenario))
    blind: list[BlindFact] = []
    for write in gold_writes(scenario):
        for arg_name, value in write.args:
            if len(value) < MIN_VALUE_LEN or value in given:
                continue
            leaves = {
                leaf
                for values in states.values()
                for leaf in values
                if leaf == value
                or (len(leaf) >= CONTAINMENT_MIN_LEN and leaf in value)
            }
            for leaf in sorted(leaves):
                if leaf in given:
                    continue
                providers = sorted(
                    app for app, values in states.items() if leaf in values)
                if not providers or len(providers) > MAX_SEAM_SOURCES:
                    continue
                if any(app in roster for app in providers):
                    continue
                blind.append(BlindFact(
                    app=write.app, function=write.function, arg=arg_name,
                    leaf=leaf, sources=tuple(providers)))
    return tuple(blind)


def admit(scenario: dict) -> Gaia2Span:
    """Measure one scenario. `usable` and `seamful` are read off the result."""
    seams = tuple(information_seams(scenario))
    return Gaia2Span(
        scenario_id=scenario_id(scenario),
        roster=derive_roster(scenario),
        write_apps=tuple(sorted({w.app for w in gold_writes(scenario)})),
        seams=seams,
        conditioned_env_events=conditioned_env_events(scenario),
        delegation_target=delegation_target(scenario),
        roster_blind=roster_blind_facts(scenario),
    )
