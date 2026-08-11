"""The charter: what a human asked the factory to build, and proof they asked.

Charter drafts may be agent-written -- by hand or by the brainstorm pathway --
but a draft has no effect until it is queued, and queueing is the approval
act. `status: draft` is what makes that gate mechanical instead of a
convention someone has to remember at 2am.

The front-matter parser is deliberately small: `key: value` lines between two
`---` fences, no nesting and no lists. The repo has no YAML dependency and
does not need one for four keys.
"""

from __future__ import annotations

from dataclasses import dataclass

_FENCE = "---"

#: Front-matter keys a charter must carry before it can be queued.
_REQUIRED = ("status", "owner")


@dataclass(frozen=True)
class Charter:
    slug: str
    owner: str
    #: Which of the three abilities this family targets, when it targets one.
    #: Free-form: the factory never branches on it, the board only displays it.
    ability: str | None
    status: str
    #: Per-job token ceiling; None means the factory's repo-level default.
    budget_tokens: int | None
    body: str


def _split_front_matter(text: str, *, slug: str) -> tuple[dict[str, str], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != _FENCE:
        raise SystemExit(
            f"{slug}: charter.md has no front-matter; it must open with a "
            f"'{_FENCE}' fence carrying at least {' and '.join(_REQUIRED)}")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == _FENCE)
    except StopIteration:
        raise SystemExit(
            f"{slug}: charter.md opens a front-matter fence that never "
            f"closes; add a '{_FENCE}' line before the body") from None
    fields: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip():
            continue
        key, sep, value = line.partition(":")
        if not sep:
            raise SystemExit(
                f"{slug}: charter.md front-matter line {line.strip()!r} is not "
                f"'key: value'; the parser reads nothing else")
        fields[key.strip()] = value.strip()
    return fields, "\n".join(lines[end + 1:]).strip()


def parse_charter(text: str, *, slug: str) -> Charter:
    """Parse and validate a charter. Refuses a draft, by name."""
    fields, body = _split_front_matter(text, slug=slug)
    for key in _REQUIRED:
        if not fields.get(key):
            raise SystemExit(
                f"{slug}: charter.md front-matter has no {key!r}; a charter "
                f"needs {' and '.join(_REQUIRED)} before it can be queued")
    if fields["status"] == "draft":
        raise SystemExit(
            f"{slug}: charter.md is still marked 'status: draft'. Queueing is "
            f"the approval act -- read it, change the status, then queue it.")
    if not body:
        raise SystemExit(
            f"{slug}: charter.md has front-matter but no body; the capability "
            f"claim and its falsifiable counterfactual are the charter")
    budget = fields.get("budget_tokens")
    return Charter(
        slug=slug,
        owner=fields["owner"],
        ability=fields.get("ability") or None,
        status=fields["status"],
        budget_tokens=int(budget) if budget else None,
        body=body,
    )
