"""Measure whether a task's apps are joined by an *information* seam.

`select.py` keeps a task when its ground truth touches >= 2 apps. That proves the
task is multi-app. It does not prove the apps have anything to say to each other,
and its own docstring claims more than it checks: "a task that cannot be
coordinated is dropped, not decorated."

The distinction this module measures:

  * **information seam** -- a fact obtained from app A is *needed* to do the work
    in app B. Only `phone` knows which contacts are roommates; only `venmo` can
    like a transaction; the names have to cross. Partitioning this trains
    delegation, because the Main has to move the fact.
  * **operation seam** -- A and B can each be worked independently and merely
    sequenced. Partitioning this trains parallel dispatch and nothing else: no
    fact crosses, so the roles are decoration.

That is the same error `select.py` was built to prevent, one level up. Counting
`supervisor.complete_task` as a collaborator turned 96 single-app puzzles into
"multi-agent" tasks; counting a merely-multi-app task as coordinatable does the
same with a second app instead of a submit channel. Both flatter the number.

**This is a heuristic, not a proof.** It is a forward taint pass with no aliasing
and no interprocedural reasoning: it can miss a seam (taint laundered through a
dict value, a `.append` into a list bound earlier) and so it *under*-reports. It
cannot invent one -- every seam it reports names the two apps and the line -- so
a task it accepts really does move a fact across. Read the number as a lower
bound on how many tasks coordinate, which is the direction that does not flatter.

Three shapes in AppWorld's ground truth that a naive pass gets wrong, all three
present in the shipped task family:

1. **APIs passed as references.** `find_all_from_pages(apis.phone.search_contacts,
   ...)` never calls the API at the call site. `select.py`'s regex
   (`apis\\.(\\w+)\\.(\\w+)\\(`) requires a paren and misses it -- `phone` only
   makes the roster of `2a163ab_1` because `access_token_from` happens to be
   called directly.
2. **Taint through helpers.** `relatives_emails = list_of(relatives, "email")`.
3. **Guard clauses.** The guarded call is not inside the `if`; the `if` body is a
   bare `continue` and the call follows it. Looking only at enclosing `if` bodies
   finds nothing.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

#: Apps that are never a coordination role, mirroring select.py.
_INFRA_APPS = frozenset({"api_docs", "admin", "supervisor"})


@dataclass(frozen=True)
class Seam:
    """A fact from `source` reaching work done in `target`."""

    source: str
    target: str
    line: int
    via: str  #: "argument" or "guard"


def _apps_in(node: ast.AST) -> set[str]:
    """Every app named by an `apis.<app>.<method>` anywhere under `node`.

    Matches the attribute, not the call, so an API handed to a helper counts.
    """
    out = set()
    for n in ast.walk(node):
        if (
            isinstance(n, ast.Attribute)
            and isinstance(n.value, ast.Attribute)
            and isinstance(n.value.value, ast.Name)
            and n.value.value.id == "apis"
        ):
            out.add(n.value.attr)
    return out - _INFRA_APPS


def _names_in(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def _taint(node: ast.AST, env: dict[str, set[str]]) -> set[str]:
    """Which apps this expression's value could carry."""
    apps = _apps_in(node)
    for name in _names_in(node):
        apps |= env.get(name, set())
    return apps


def _bind(target: ast.AST, apps: set[str], env: dict[str, set[str]]) -> None:
    """Taint every name a binding target introduces. Tuples taint elementwise."""
    for n in ast.walk(target):
        if isinstance(n, ast.Name):
            env[n.id] = set(apps)


def _is_guard_clause(stmt: ast.stmt) -> bool:
    """`if cond: continue` -- the pattern that guards what comes *after* it."""
    return (
        isinstance(stmt, ast.If)
        and not stmt.orelse
        and all(isinstance(s, (ast.Continue, ast.Break, ast.Return, ast.Pass))
                for s in stmt.body)
    )


def _calls_in(node: ast.AST) -> list[tuple[str, ast.Call]]:
    """Direct `apis.<app>.<method>(...)` calls under `node`, with their app."""
    out = []
    for n in ast.walk(node):
        if (
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and isinstance(n.func.value, ast.Attribute)
            and isinstance(n.func.value.value, ast.Name)
            and n.func.value.value.id == "apis"
        ):
            app = n.func.value.attr
            if app not in _INFRA_APPS:
                out.append((app, n))
    return out


def _walk(body: list[ast.stmt], env: dict[str, set[str]], guard: set[str],
          seams: list[Seam]) -> None:
    """Walk a statement list, accumulating guard taint from guard clauses."""
    guard = set(guard)
    for stmt in body:
        # A call's *arguments* carry taint directly; the guards in scope carry it
        # indirectly -- both mean the work in `app` needed a fact from elsewhere.
        for app, call in _calls_in(stmt):
            arg_apps: set[str] = set()
            for a in list(call.args) + [k.value for k in call.keywords]:
                arg_apps |= _taint(a, env)
            for src in sorted(arg_apps - {app}):
                seams.append(Seam(src, app, call.lineno, "argument"))
            for src in sorted(guard - {app} - arg_apps):
                seams.append(Seam(src, app, call.lineno, "guard"))

        if _is_guard_clause(stmt):
            # Everything after it in this block is conditional on the test.
            guard |= _taint(stmt.test, env)
            continue

        if isinstance(stmt, ast.Assign):
            apps = _taint(stmt.value, env)
            for t in stmt.targets:
                _bind(t, apps, env)
        elif isinstance(stmt, (ast.AugAssign, ast.AnnAssign)) and stmt.value:
            _bind(stmt.target, _taint(stmt.value, env), env)
        elif isinstance(stmt, ast.For):
            _bind(stmt.target, _taint(stmt.iter, env), env)
            _walk(stmt.body, env, guard, seams)
            _walk(stmt.orelse, env, guard, seams)
        elif isinstance(stmt, ast.While):
            _walk(stmt.body, env, guard | _taint(stmt.test, env), seams)
        elif isinstance(stmt, ast.If):
            inner = guard | _taint(stmt.test, env)
            _walk(stmt.body, env, inner, seams)
            _walk(stmt.orelse, env, inner, seams)
        elif isinstance(stmt, (ast.With, ast.Try)):
            _walk(getattr(stmt, "body", []), env, guard, seams)


def seams_of(solution_code: str) -> list[Seam]:
    """Every information seam the ground truth actually crosses.

    Returns an empty list for a task whose apps never exchange a fact -- an
    operation seam, which a partition would decorate rather than test.
    """
    try:
        tree = ast.parse(solution_code)
    except SyntaxError:
        return []

    seams: list[Seam] = []
    for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
        _walk(fn.body, {}, set(), seams)

    # Dedupe: the same (source -> target) many times is one seam.
    out: dict[tuple[str, str], Seam] = {}
    for s in seams:
        out.setdefault((s.source, s.target), s)
    return sorted(out.values(), key=lambda s: (s.line, s.source, s.target))


def has_information_seam(solution_code: str) -> bool:
    return bool(seams_of(solution_code))
