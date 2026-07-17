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
dict value, a `.append` into a list bound earlier) and so it *under*-reports.
Sibling branches are analyzed independently, so one branch cannot lend a value
to another. Loop bodies do propagate taint: these are reference solutions over a
fixed task state, and several valid solutions intentionally bind a value while
searching a non-empty collection and consume it afterwards. Every reported seam
still names the two apps and the consuming line. Read the number as a tested
heuristic, not as a formally verified dependency graph.

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
from collections import Counter
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


def _statement_expressions(stmt: ast.stmt) -> list[ast.AST]:
    """Expressions owned by this statement, excluding nested statement bodies."""
    if isinstance(stmt, ast.Expr):
        return [stmt.value]
    if isinstance(stmt, ast.Assign):
        return [stmt.value]
    if isinstance(stmt, ast.AnnAssign):
        return [node for node in (stmt.annotation, stmt.value) if node is not None]
    if isinstance(stmt, ast.AugAssign):
        return [stmt.target, stmt.value]
    if isinstance(stmt, (ast.For, ast.AsyncFor)):
        return [stmt.iter]
    if isinstance(stmt, (ast.While, ast.If)):
        return [stmt.test]
    if isinstance(stmt, (ast.With, ast.AsyncWith)):
        return [item.context_expr for item in stmt.items]
    if isinstance(stmt, ast.Assert):
        return [node for node in (stmt.test, stmt.msg) if node is not None]
    if isinstance(stmt, ast.Return):
        return [stmt.value] if stmt.value is not None else []
    if isinstance(stmt, ast.Raise):
        return [node for node in (stmt.exc, stmt.cause) if node is not None]
    return []


def _copy_env(env: dict[str, set[str]]) -> dict[str, set[str]]:
    return {name: set(apps) for name, apps in env.items()}


def _join_envs(
    base: dict[str, set[str]], branches: list[dict[str, set[str]]]
) -> dict[str, set[str]]:
    """Join possible taint after analyzing sibling branches independently.

    This is a may-analysis over trusted reference solutions: if either branch can
    bind a value from an app, a later consumer may depend on that app. The
    branches are not allowed to borrow each other's bindings while they are
    analyzed, which is the false-positive case this separation prevents.
    """
    if not branches:
        return _copy_env(base)
    out: dict[str, set[str]] = {}
    names = set(base).union(*(set(branch) for branch in branches))
    for name in names:
        apps = set(base.get(name, set()))
        for branch in branches:
            apps |= branch.get(name, set())
        out[name] = apps
    return out


def _walk(body: list[ast.stmt], env: dict[str, set[str]], guard: set[str],
          seams: list[Seam]) -> None:
    """Walk a statement list, accumulating guard taint from guard clauses."""
    guard = set(guard)
    for stmt in body:
        # A call's *arguments* carry taint directly; the guards in scope carry it
        # indirectly -- both mean the work in `app` needed a fact from elsewhere.
        for expression in _statement_expressions(stmt):
            for app, call in _calls_in(expression):
                arg_apps: set[str] = set()
                for argument in list(call.args) + [
                    keyword.value for keyword in call.keywords
                ]:
                    arg_apps |= _taint(argument, env)
                seams.extend(
                    Seam(source, app, call.lineno, "argument")
                    for source in sorted(arg_apps - {app})
                )
                seams.extend(
                    Seam(source, app, call.lineno, "guard")
                    for source in sorted(guard - {app} - arg_apps)
                )

        if _is_guard_clause(stmt):
            # Everything after it in this block is conditional on the test.
            assert isinstance(stmt, ast.If)
            guard |= _taint(stmt.test, env)
            continue

        if isinstance(stmt, ast.Assign):
            apps = _taint(stmt.value, env)
            for t in stmt.targets:
                _bind(t, apps, env)
        elif isinstance(stmt, (ast.AugAssign, ast.AnnAssign)) and stmt.value:
            _bind(stmt.target, _taint(stmt.value, env), env)
        elif isinstance(stmt, ast.For):
            body_env = _copy_env(env)
            _bind(stmt.target, _taint(stmt.iter, env), body_env)
            _walk(stmt.body, body_env, guard, seams)
            _walk(stmt.orelse, body_env, guard, seams)
            env.clear()
            env.update(body_env)
        elif isinstance(stmt, ast.While):
            body_env = _copy_env(env)
            _walk(stmt.body, body_env, guard | _taint(stmt.test, env), seams)
            _walk(stmt.orelse, body_env, guard, seams)
            env.clear()
            env.update(body_env)
        elif isinstance(stmt, ast.If):
            inner = guard | _taint(stmt.test, env)
            body_env = _copy_env(env)
            _walk(stmt.body, body_env, inner, seams)
            else_env = _copy_env(env)
            _walk(stmt.orelse, else_env, inner, seams)
            joined = _join_envs(env, [body_env, else_env])
            env.clear()
            env.update(joined)
        elif isinstance(stmt, (ast.With, ast.AsyncWith)):
            inner = _copy_env(env)
            for item in stmt.items:
                if item.optional_vars is not None:
                    _bind(item.optional_vars, _taint(item.context_expr, env), inner)
            _walk(stmt.body, inner, guard, seams)
            env.clear()
            env.update(inner)
        elif isinstance(stmt, ast.Try):
            body_env = _copy_env(env)
            _walk(stmt.body, body_env, guard, seams)
            _walk(stmt.orelse, body_env, guard, seams)
            branches = [body_env]
            for handler in stmt.handlers:
                handler_env = _copy_env(env)
                _walk(handler.body, handler_env, guard, seams)
                branches.append(handler_env)
            joined = _join_envs(env, branches)
            _walk(stmt.finalbody, joined, guard, seams)
            env.clear()
            env.update(joined)


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


def information_seam_task_ids(
    span_rows: list[dict], seam_rows: list[dict]
) -> set[str]:
    """Join roster and seam measurements, refusing drift or partial files.

    The two files are intentionally separate evidence artifacts: one records
    which apps a reference solution touches, the other records whether a fact
    actually crosses between them. Rendering from their unchecked intersection
    would let a stale or partial seam file silently shrink the candidate pool.
    """
    if any(not isinstance(row.get("task_id"), str) for row in span_rows):
        raise ValueError("span measurement contains a row without a task_id")
    if any(not isinstance(row.get("task_id"), str) for row in seam_rows):
        raise ValueError("seam measurement contains a row without a task_id")

    span_counts = Counter(row["task_id"] for row in span_rows)
    seam_counts = Counter(row["task_id"] for row in seam_rows)
    duplicate_span = sorted(task for task, count in span_counts.items() if count != 1)
    duplicate_seams = sorted(task for task, count in seam_counts.items() if count != 1)
    if duplicate_span or duplicate_seams:
        raise ValueError(
            "selection files contain duplicate task ids: "
            f"span={duplicate_span[:3]}, seams={duplicate_seams[:3]}"
        )

    span_by_id = {row["task_id"]: row for row in span_rows}
    seam_by_id = {row["task_id"]: row for row in seam_rows}
    missing = sorted(set(span_by_id) - set(seam_by_id))
    extra = sorted(set(seam_by_id) - set(span_by_id))
    if missing or extra:
        raise ValueError(
            "selection files describe different task sets: "
            f"missing from seams={missing[:3]}, extra in seams={extra[:3]}"
        )

    for task_id, span in span_by_id.items():
        if span.get("roster") != seam_by_id[task_id].get("roster"):
            raise ValueError(
                f"{task_id}: roster differs between span and seam measurements; "
                "rerun both commands before rendering"
            )
    return {task_id for task_id, row in seam_by_id.items() if row.get("seams")}
