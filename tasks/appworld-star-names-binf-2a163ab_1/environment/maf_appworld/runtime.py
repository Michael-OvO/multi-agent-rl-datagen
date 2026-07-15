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
from dataclasses import dataclass, field

from forge.appworld.partition import Constraints, Topology, Visibility

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


_SPECIALIST_SYSTEM = """You are the {app} specialist. You are one of several app \
specialists on a team.

You can use ONLY `apis.{app}.*`, plus `apis.supervisor.*` for credentials and \
`apis.api_docs.*` for documentation. You cannot see or use any other app. You do \
NOT know the team's overall task -- only the request your coordinator sends you.

If the request needs a fact you have no way to obtain from {app}, say so plainly \
instead of guessing. Substituting something that looks similar is worse than \
reporting that you cannot answer.

Workflow:
1. Call `apis.api_docs.show_api_descriptions(app_name='{app}')` first. Do not \
guess API names.
2. Call `apis.api_docs.show_api_doc(app_name='{app}', api_name=...)` for exact \
parameters.
3. Log in: password from `apis.supervisor.show_account_passwords()`, email from \
`apis.supervisor.show_profile()`.
4. Do the work. Paginate when a list API takes page_index.

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


def run_specialist(
    client, world, app: str, brief: str, log: RunLog, model: str = DEFAULT_MODEL,
    max_turns: int = 14,
) -> str:
    """Run one specialist against a brief. Returns its one-line report."""
    msgs = [
        {"role": "system", "content": _SPECIALIST_SYSTEM.format(app=app)},
        {"role": "user", "content": f"Coordinator's request:\n{brief}"},
    ]
    for _ in range(max_turns):
        out = chat(client, msgs, model=model)
        msgs.append({"role": "assistant", "content": out})
        code = extract_code(out)
        if code.startswith("FINAL:"):
            report = code[len("FINAL:") :].strip()
            if re.search(r"\bcannot\b|\bno way\b|\bunable\b|\bdon't have\b", report, re.I):
                log.refusals += 1
            return report
        result = world.execute(code)
        log.specialist_turns += 1
        # Specialist context grows fast because API docs are verbose; truncate
        # what we feed back or we hit the TPM ceiling on every task.
        msgs.append({"role": "user", "content": f"Output:\n{str(result)[:2500]}"})
    return "(no answer within turn limit)"


def _main_system(constraints: Constraints, capability_note: str) -> str:
    if constraints.topology is Topology.CHAIN:
        routing = (
            f"You may delegate ONLY to {constraints.roster[0]}. Specialists hand off "
            "down the chain themselves: " + " -> ".join(constraints.roster)
        )
    else:
        routing = "You may delegate to: " + ", ".join(constraints.roster)

    budget = (
        "You have unlimited delegations."
        if constraints.delegation_budget is None
        else f"You may delegate at most {constraints.delegation_budget} times. Plan before you spend."
    )

    return f"""You are the Main coordinator. You have NO tools and NO API access. \
You cannot touch any app yourself. Everything must be done by a specialist.

{routing}
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
    note = (
        "You know only their names, not what they can do. Ask them if you need to know."
        if constraints.visibility is Visibility.NAMES
        else "Their capabilities are listed above."
    )
    msgs = [
        {"role": "system", "content": _main_system(constraints, note)},
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
