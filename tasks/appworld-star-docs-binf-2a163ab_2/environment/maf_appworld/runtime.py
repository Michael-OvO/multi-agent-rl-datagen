"""The Main and the app specialists.

Everything here is *environment*, except the Main, which is the model under test.

The specialists are real LLMs, and that is deliberate. If a specialist were a
scripted executor of structured requests, the Main would just be calling APIs
with extra steps and the multi-agent structure would be theatre. A specialist
has to interpret a natural-language brief for "did the Main brief it well" to
mean anything -- and once it does, a vague brief produces wrong work, which
AppWorld's state check catches for free. That is how communication quality gets
graded without an LLM judge.

Observed on the first two prototype runs (2026-07-15), unprompted: asked "list my
roommates" the venmo specialist, which has no address book, substituted its
friends list and answered confidently. The Main never queried `phone`, which is
the only app that knows. The oracle catches the resulting wrong likes. We did not
design that failure; it fell out of the access constraint.
"""

from __future__ import annotations

import random
import re
import time
from collections.abc import Iterable
from dataclasses import dataclass, field

from forge.appworld.partition import Constraints, Topology, Visibility
from forge.appworld.sandbox import bound_names, inspect_code

DEFAULT_MODEL = "gpt-4.1"

# The org TPM ceiling is low relative to specialist transcripts (they carry API
# docs), so 429s are routine rather than exceptional. Transient httpx timeouts
# also occur. Retry both; let everything else surface.
_RETRYABLE = ("rate_limit", "429", "timeout", "timed out", "connection")


#: Models that reject `temperature=0` (they only accept the default). Discovered
#: the hard way: every call 400'd, the caller swallowed it, and three rollouts
#: reported `turns=0` with a plausible-looking score instead of an error.
_NO_TEMPERATURE: set[str] = set()


def chat(client, messages: list[dict], model: str = DEFAULT_MODEL, retries: int = 6) -> str:
    for attempt in range(retries):
        kwargs: dict = {"model": model, "messages": messages}
        if model not in _NO_TEMPERATURE:
            kwargs["temperature"] = 0
        try:
            r = client.chat.completions.create(**kwargs)
            return r.choices[0].message.content or ""
        except Exception as e:
            msg = str(e).lower()
            if "temperature" in msg and "unsupported" in msg:
                _NO_TEMPERATURE.add(model)  # retry immediately without it
                continue
            if not any(t in msg for t in _RETRYABLE) or attempt == retries - 1:
                raise
            time.sleep(min(2**attempt + random.random(), 30))
    raise RuntimeError("unreachable")


def extract_code(text: str) -> str:
    m = re.search(r"```(?:python)?\s*(.*?)```", text, re.S)
    return (m.group(1) if m else text).strip()


#: How much of an execution's output the specialist may see.
#:
#: This was 2500, chosen to survive the TPM ceiling, and it silently destroyed
#: the dimension. Every specialist's first act is
#: `apis.api_docs.show_api_descriptions(...)`; venmo's catalog is 5,444
#: characters; so the cap cut the catalog mid-JSON and deleted 30 of its 54 APIs
#: -- among them `like_transaction` and `show_social_feed`, which is what the
#: shipped tasks *are*. The specialist was told "do not guess API names" and then
#: handed a list without the verb it needed. It reported that the API did not
#: exist, which was the truth about what it had been shown.
#:
#: That is the 0.333 in WRITEUP.md §5: not a hard task, a hidden API.
#: Measured in sweep/appworld_api_catalog.json; the floor it coincides with is in
#: sweep/appworld_donothing.json. Any value here below the largest catalog is a
#: silent correctness bug, and a test pins it against the measured file.
MAX_OUTPUT_CHARS = 12000


def execution_feedback(result) -> str:
    """What the specialist is shown after running code.

    Truncation still exists -- specialist transcripts really do grow fast enough
    to matter -- but it announces itself. A specialist that knows its output was
    cut can paginate; one that does not concludes the world is smaller than it
    is.
    """
    text = str(result)
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    withheld = len(text) - MAX_OUTPUT_CHARS
    return (text[:MAX_OUTPUT_CHARS]
            + f"\n\n[output truncated: {withheld} characters withheld. If you were "
              f"listing APIs or paging results, narrow the query and try again -- "
              f"do NOT conclude that what you cannot see does not exist.]")


def _specialist_system(apps: tuple[str, ...]) -> str:
    """The specialist's entire world, rendered.

    `apps` is one app for a real specialist, or **the whole roster** for the OPEN
    control -- one agent holding everything, which exists so a partitioned score
    has a ruler.

    The control used to be rendered by joining its roster into the old `{app}`
    slot with backticks (`"phone`, `apis.venmo"`), so the prose would read right.
    The prose did. The workflow did not: it emitted
    `show_api_descriptions(app_name='phone`, `apis.venmo')`, which cannot run, so
    the control has never once been shown a catalog. It scored 1.000 anyway, by
    guessing API names -- which is worth knowing about the control, and was
    invisible while the string looked fine.
    """
    label = apps[0] if len(apps) == 1 else " + ".join(apps)
    surface = ", ".join(f"`apis.{a}.*`" for a in apps)
    catalogs = "\n".join(
        f"   print(apis.api_docs.show_api_descriptions(app_name={a!r}))"
        for a in apps)
    theirs = f"`{apps[0]}`" if len(apps) == 1 else "the apps you hold"

    return f"""You are the {label} specialist. You are one of several app \
specialists on a team.

You can use ONLY {surface}, plus `apis.supervisor.*` for credentials and \
`apis.api_docs.*` for documentation. You cannot see or use any other app. You do \
NOT know the team's overall task -- only the request your coordinator sends you.

If the request needs a fact you have no way to obtain from {theirs}, say so \
plainly instead of guessing. Substituting something that looks similar is worse \
than reporting that you cannot answer.

You only ever see **standard output**. A bare expression shows you NOTHING -- it \
reports "Execution successful." and no data. `print(...)` everything you want to \
read.

Workflow:
1. Read your catalog first, and do not guess API names:
{catalogs}
2. `print(apis.api_docs.show_api_doc(app_name=..., api_name=...))` for exact \
parameters.
3. Log in: password from `print(apis.supervisor.show_account_passwords())`, email \
from `print(apis.supervisor.show_profile())`.
4. Do the work. Paginate when a list API takes page_index.

If output says it was truncated, narrow the query -- do not conclude that what \
you did not see does not exist.

Reply with ONLY a fenced python block. After each block you will see its output \
and may send another. When finished, reply with a block containing only:
    FINAL: <one line: what you found or did, or why you could not>
"""


@dataclass
class Interaction:
    """One message across a channel, for the trajectory record."""

    sender: str
    receiver: str
    content: str
    reply: str = ""


@dataclass
class RunLog:
    interactions: list[Interaction] = field(default_factory=list)
    specialist_turns: int = 0
    delegations: int = 0
    refusals: int = 0  # specialist declined rather than guessed
    #: Specialist turns refused by the sandbox before execution. Non-zero means
    #: a brief talked a specialist outside its app -- worth reading, because the
    #: Main writes the briefs and an RL Main will find this if it pays.
    blocked: int = 0
    #: Why, not just how many. A bare count told us the gate had refused
    #: *something* on a run that still scored 1.0, and nothing could say what --
    #: it turned out to be the specialist's own login token (§7.4: log the names).
    blocked_reasons: list[str] = field(default_factory=list)


def run_specialist(
    client, world, app: str | Iterable[str], brief: str, log: RunLog,
    model: str = DEFAULT_MODEL, max_turns: int = 14,
) -> str:
    """Run one specialist against a brief. Returns its one-line report.

    `app` is a single app, or several for the OPEN control (one agent, whole
    roster). Both the prompt and the sandbox derive from it, so passing the apps
    as apps -- rather than as a pre-formatted display string -- is what keeps the
    two from disagreeing.
    """
    apps = (app,) if isinstance(app, str) else tuple(app)
    msgs = [
        {"role": "system", "content": _specialist_system(apps)},
        {"role": "user", "content": f"Coordinator's request:\n{brief}"},
    ]
    # AppWorld's shell keeps its namespace between execute() calls, so names the
    # specialist bound on an accepted turn are its own on the next one. Only
    # accepted turns contribute: a refused turn never ran, so it bound nothing.
    session: set[str] = set()
    for _ in range(max_turns):
        out = chat(client, msgs, model=model)
        msgs.append({"role": "assistant", "content": out})
        code = extract_code(out)
        if code.startswith("FINAL:"):
            report = code[len("FINAL:") :].strip()
            if re.search(r"\bcannot\b|\bno way\b|\bunable\b|\bdon't have\b", report, re.I):
                log.refusals += 1
            return report
        # The app boundary is decided here, before execution, because the Main
        # authors the brief and the system prompt above is only a request.
        refusal = inspect_code(code, apps, known=session)
        if refusal is not None:
            log.blocked += 1
            log.blocked_reasons.append(refusal)
            msgs.append({"role": "user", "content": f"Output:\nRefused: {refusal}"})
            continue

        session |= bound_names(code)
        result = world.execute(code)
        log.specialist_turns += 1
        msgs.append({"role": "user",
                     "content": f"Output:\n{execution_feedback(result)}"})
    return "(no answer within turn limit)"


def _main_system(
    constraints: Constraints, capability_note: str, catalogs: dict[str, str] | None = None
) -> str:
    if constraints.topology is Topology.CHAIN:
        routing = (
            f"You may delegate ONLY to {constraints.roster[0]}. Specialists hand off "
            "down the chain themselves: " + " -> ".join(constraints.roster)
        )
    else:
        routing = "You may delegate to: " + ", ".join(constraints.roster)

    # The DOCS arm's note says "listed above", so something has to be above it.
    # It said that for the whole of the v3 sweep with nothing above it but the
    # names -- so `visibility` was measured as one sentence against another, one
    # of which was false, and the shipped container (which really does serve
    # catalogs over `team docs`) was never what the sweep ran. Never truncate
    # these: a 2500-char cap on the *specialist's* catalog is what deleted
    # `like_transaction` and produced the 0.333 that got written up as
    # difficulty (see MAX_OUTPUT_CHARS).
    listing = ""
    if catalogs:
        listing = "\n\nYour specialists' API catalogs:\n\n" + "\n\n".join(
            f"--- {app} ---\n{cat}" for app, cat in catalogs.items()
        )

    budget = (
        "You have unlimited delegations."
        if constraints.delegation_budget is None
        else f"You may delegate at most {constraints.delegation_budget} times. Plan before you spend."
    )

    return f"""You are the Main coordinator. You have NO tools and NO API access. \
You cannot touch any app yourself. Everything must be done by a specialist.

{routing}{listing}
{capability_note}
{budget}

Each specialist can use ONLY its own app and does NOT know your task.

To act, reply with EXACTLY one line:
    DELEGATE <specialist> :: <your request in plain English>

Rules that decide whether you succeed:
- A specialist cannot see other apps. If a request needs a fact that lives in a \
different app, YOU must obtain that fact first and put it in the request.
- Some specialists cannot possibly know some things. Ask the one that can.
- Be specific. A vague request produces vague work.

When the task is fully done, reply with exactly:
    DONE :: <one-line answer, or 'completed' if the task was an action>
"""


def run_main(
    client, world, task: str, constraints: Constraints, log: RunLog,
    model: str = DEFAULT_MODEL, sub_model: str | None = None, max_steps: int = 12,
) -> str:
    """Run the Main. Returns its final answer string."""
    names_only = constraints.visibility is Visibility.NAMES
    note = (
        "You know only their names, not what they can do. Ask them if you need to know."
        if names_only
        else "Their capabilities are listed above."
    )
    # Fetched the same way the shipped sidecar's /roster does it, so that the
    # in-process sweep and the container measure the same configuration.
    catalogs = (
        None
        if names_only
        else {
            app: world.execute(
                f"print(apis.api_docs.show_api_descriptions(app_name={app!r}))")
            for app in constraints.roster
        }
    )
    msgs = [
        {"role": "system", "content": _main_system(constraints, note, catalogs)},
        {"role": "user", "content": f"Task from your supervisor:\n{task}"},
    ]

    for _ in range(max_steps):
        out = chat(client, msgs, model=model).strip()
        msgs.append({"role": "assistant", "content": out})

        if out.startswith("DONE"):
            return out.split("::", 1)[1].strip() if "::" in out else "completed"

        m = re.match(r"DELEGATE\s+(\w+)\s*::\s*(.+)", out, re.S)
        if not m:
            msgs.append({"role": "user", "content":
                         "Malformed. Use 'DELEGATE <name> :: <request>' or 'DONE :: <answer>'."})
            continue

        who, brief = m.group(1), m.group(2).strip()
        allowed = constraints.allowed_targets("main")
        if who not in allowed:
            # The topology is enforced here, not requested politely.
            msgs.append({"role": "user", "content":
                         f"You cannot reach {who}. You may delegate to: {list(allowed)}"})
            continue
        if (constraints.delegation_budget is not None
                and log.delegations >= constraints.delegation_budget):
            msgs.append({"role": "user", "content":
                         "Delegation budget exhausted. Reply DONE :: <answer>."})
            continue

        log.delegations += 1
        reply = run_specialist(client, world, who, brief, log,
                               model=sub_model or model)
        log.interactions.append(Interaction("main", who, brief, reply))
        msgs.append({"role": "user", "content": f"{who} reports: {reply}"})

    return "(out of steps)"
