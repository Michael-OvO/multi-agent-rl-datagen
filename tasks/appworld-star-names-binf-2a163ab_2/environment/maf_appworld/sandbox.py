"""What a specialist's code is allowed to touch, decided before it runs.

`run_specialist` hands model-written Python to `world.execute()`. The Main writes
the brief that produces that Python, so without this gate the specialist's app
boundary is only as strong as its system prompt -- and the Main has every
incentive to talk its way past it.

AppWorld's own `SafetyGuard` does not close this. It allows `os` outright, and
its per-module denylists name *functions*, so `os.environ` (a mapping) was never
covered. `execute()` runs in-process (`_shell_run_cell`), which puts the sidecar's
`MAF_VERIFIER_TOKEN` and `OPENAI_API_KEY` one `print` away from the specialist's
transcript and, via its report, from the Main. None of that is a bug in AppWorld:
its guard exists to stop a *benign* agent damaging the host, and its source says
so. Containing an adversarial Main is our problem, so it is solved here.

## The rule, and why it is this rule

**Every name the code did not create itself must be one we permit.** Names the
code binds -- variables, loop and comprehension targets, function names and their
arguments, imports, `except ... as` -- are its own business. Every *free* name
resolves against the execution namespace, and that namespace is not ours: it is
whatever AppWorld and IPython decided to put there.

The first version of this gate enumerated dangerous names instead. That is a
denylist, and a denylist holds only against what its author thought of. It did
not hold, and the misses were not exotic:

  * `requester` -- AppWorld binds a second API client into the namespace
    (`environment.py:430`). A boundary enforced over `apis.*` never mentions it.
  * `get_ipython` -- the shell is `InteractiveShellEmbed`, so the interpreter is
    reachable by name. `get_ipython().run_cell("import os; print(os.environ[...])")`
    hides the payload in a *string literal*: there is no `import os` in the AST
    to see, only a method call on a name nobody had banned. Measured: it printed
    the token. So did `get_ipython().ev(...)`.

Both were already there, and both were missed, which is the argument. Default-deny
is not stricter book-keeping — it is the only version of this check that covers
what the *next* AppWorld release binds into that namespace without telling us.

Unparseable input is refused rather than waved through. `!env` and `%magic` are
IPython escapes, not Python; today AppWorld's own `ast.parse` rejects them before
`run_cell` ever sees them, but that is a dependency's internal ordering and this
gate is not entitled to lean on it.

Default-deny applies to attributes too, and that took a second pass to get
right. The first version banned `os`, `sys` and `subprocess` as *names* and
filtered attributes with one pattern (`__*`) -- a denylist, inside the file
arguing against denylists. It did not hold either, and again the misses were
not exotic: `uuid.os` **is** the `os` module, `pprint._sys` is `sys`, and
`from uuid import os` skips the attribute chain altogether. Measured 2026-07-17:
`uuid.os.environ[...]` read the verifier token past this gate. Which modules
re-export which is an interpreter detail that moves between releases, so
`_module_attrs` computes it rather than listing it.

## What this gate does not close

**A static gate is defense in depth, not process isolation.** This one now tracks
bindings by lexical scope and control flow: a module-level name is available only
after a binding that must have executed, comprehension and lambda variables do
not leak into their parent scope, and names from a prior turn are carried forward
only when that turn completed successfully. A dead branch, a later assignment,
or a nested function parameter therefore cannot make an AppWorld namespace name
look user-created.

That closes the concrete namespace-laundering failures this repository measured.
It does not make arbitrary in-process Python equivalent to a separate sandbox:
Python's object model and the execution namespace still belong to a dependency.
The durable containment boundary remains the sidecar process and its stripped
environment; moving each specialist execution into its own process would be a
further hardening step, not a claim this AST pass makes.

So this is not the only lock. The sidecar pops its secrets out of `os.environ`
at startup (`container/server.py`), which is what makes the environment not
worth reading even when this gate is bypassed -- and it is why the 2026-07-17
finding was a token in module globals rather than a token in `os.environ`.
`scripts/appworld_injection_probe.py` runs the exploits both ways to keep this
file honest.
"""

from __future__ import annotations

import ast
import importlib
import types
from collections.abc import Iterable
from functools import cache

#: Every specialist needs credentials and API discovery; neither reveals another
#: app's *data*, which is what the partition is about.
_SHARED_APPS = ("supervisor", "api_docs")

#: Deliberately small. A specialist's work is API calls; this is for shaping
#: their results. `os`, `sys`, `subprocess`, `importlib` are absent on purpose.
_ALLOWED_IMPORTS = frozenset({
    "collections", "datetime", "decimal", "functools", "itertools", "json",
    "math", "pprint", "re", "statistics", "string", "textwrap", "uuid",
})

#: Builtins a specialist has a real use for. Everything that reaches outside the
#: given namespace is simply absent rather than listed: `eval`, `exec`,
#: `compile`, `globals`, `locals`, `vars`, `dir`, `getattr`, `setattr`, `open`,
#: `input`, `__import__`, `breakpoint`. Under default-deny they need no entry --
#: and neither does the next one nobody thought of.
_ALLOWED_BUILTINS = frozenset({
    "abs", "all", "any", "bool", "dict", "divmod", "enumerate", "filter",
    "float", "format", "frozenset", "int", "isinstance", "len", "list", "map",
    "max", "min", "next", "print", "range", "repr", "reversed", "round", "set",
    "slice", "sorted", "str", "sum", "tuple", "zip",
    # Enough to write a sane try/except around an API call.
    "AttributeError", "Exception", "IndexError", "KeyError", "RuntimeError",
    "StopIteration", "TypeError", "ValueError", "ZeroDivisionError",
})


@cache
def _module_attrs(module: str) -> frozenset[str]:
    """Which of `module`'s attributes are themselves modules.

    Computed from the running interpreter, never enumerated. An allowlisted
    module binds the banned ones as ordinary attributes -- `uuid.os` is the `os`
    module, `pprint._sys` is `sys` -- and which ones it binds is an
    implementation detail that moves between Python releases. The sidecar is
    3.11 and the sweep host is 3.13; a literal list would be right in one and
    quietly wrong in the other, which is the drift `test_environment.py` exists
    to prevent for the pins.

    Measured 2026-07-17 on 3.13: 8 of the 13 allowlisted modules re-export
    something, and `os`, `sys` and `codecs` are all reachable. `sys` is the whole
    game -- `sys.modules` reaches every loaded module, including the sidecar's
    own, whose globals still hold the token that `server.py` popped out of the
    environment.

    A module that will not import yields nothing rather than raising: this runs
    at gate time, and a gate that crashes on an exotic build fails open.
    """
    try:
        mod = importlib.import_module(module)
    except Exception:
        return frozenset()
    return frozenset(
        name for name in dir(mod)
        if isinstance(getattr(mod, name, None), types.ModuleType)
    )


def _target_names(target: ast.AST) -> set[str]:
    """Names introduced by one assignment target, without crossing scopes."""
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        out: set[str] = set()
        for item in target.elts:
            out |= _target_names(item)
        return out
    return set()


def _argument_names(args: ast.arguments) -> set[str]:
    return {
        arg.arg
        for arg in (
            list(args.posonlyargs)
            + list(args.args)
            + list(args.kwonlyargs)
            + ([args.vararg] if args.vararg else [])
            + ([args.kwarg] if args.kwarg else [])
        )
    }


class _FunctionLocals(ast.NodeVisitor):
    """Collect names Python makes local to one function scope.

    Python decides function locals for the whole body at compile time, so a load
    before a local assignment raises ``UnboundLocalError``; it does not fall
    through to AppWorld's namespace. Nested scopes and comprehensions have their
    own rules and must not contribute names to the containing function.
    """

    def __init__(self, args: ast.arguments) -> None:
        self.names = _argument_names(args)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self.names.add(node.id)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.names.add(node.name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.names.add(node.name)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.names.add(node.name)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return

    def _visit_comprehension(
        self,
        node: ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp,
    ) -> None:
        # Iterables and filters may refer to outer locals; targets and result
        # expressions live in the comprehension's nested scope.
        for generator in node.generators:
            self.visit(generator.iter)

    visit_ListComp = _visit_comprehension
    visit_SetComp = _visit_comprehension
    visit_DictComp = _visit_comprehension
    visit_GeneratorExp = _visit_comprehension

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.names.add(alias.asname or alias.name.split(".")[0])

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            self.names.add(alias.asname or alias.name)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name:
            self.names.add(node.name)
        for stmt in node.body:
            self.visit(stmt)


def _function_locals(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    collector = _FunctionLocals(node.args)
    for stmt in node.body:
        collector.visit(stmt)
    return collector.names


def _name_error(
    node: ast.Name,
    available: set[str],
    cleared_apis: set[int],
    *,
    allow_unknown: bool,
) -> str | None:
    if not isinstance(node.ctx, ast.Load) or allow_unknown:
        return None
    if node.id == "apis":
        if id(node) in cleared_apis:
            return None
        return "`apis` may be used only as `apis.<specialist>.<call>`."
    if node.id in available:
        return None
    return (
        f"the name {node.id!r} is not available to you. You may use your own "
        "variables, `apis.<specialist>.<call>`, and the standard library "
        "modules you import."
    )


def _check_expr(
    node: ast.AST | None,
    available: set[str],
    cleared_apis: set[int],
    *,
    allow_unknown: bool,
) -> str | None:
    """Check one expression without leaking bindings into its parent scope."""
    if node is None:
        return None
    if isinstance(node, ast.Name):
        return _name_error(
            node, available, cleared_apis, allow_unknown=allow_unknown
        )
    if isinstance(node, ast.NamedExpr):
        # Correctly propagating a walrus requires expression-level dominance
        # analysis. Specialists do not need it, and guessing would recreate the
        # exact namespace-laundering class this pass exists to close.
        return None if allow_unknown else "assignment expressions (`:=`) are not permitted."
    if isinstance(node, ast.Lambda):
        for default in list(node.args.defaults) + [
            value for value in node.args.kw_defaults if value is not None
        ]:
            error = _check_expr(
                default,
                available,
                cleared_apis,
                allow_unknown=allow_unknown,
            )
            if error:
                return error
        return _check_expr(
            node.body,
            available | _argument_names(node.args),
            cleared_apis,
            allow_unknown=allow_unknown,
        )
    if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
        inner = set(available)
        for generator in node.generators:
            error = _check_expr(
                generator.iter,
                inner,
                cleared_apis,
                allow_unknown=allow_unknown,
            )
            if error:
                return error
            inner |= _target_names(generator.target)
            for condition in generator.ifs:
                error = _check_expr(
                    condition,
                    inner,
                    cleared_apis,
                    allow_unknown=allow_unknown,
                )
                if error:
                    return error
        outputs = (
            (node.key, node.value)
            if isinstance(node, ast.DictComp)
            else (node.elt,)
        )
        for output in outputs:
            error = _check_expr(
                output,
                inner,
                cleared_apis,
                allow_unknown=allow_unknown,
            )
            if error:
                return error
        return None

    for child in ast.iter_child_nodes(node):
        error = _check_expr(
            child,
            available,
            cleared_apis,
            allow_unknown=allow_unknown,
        )
        if error:
            return error
    return None


def _check_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    available: set[str],
    cleared_apis: set[int],
    *,
    allow_unknown: bool,
) -> str | None:
    outer_expressions = (
        list(node.decorator_list)
        + list(node.args.defaults)
        + [value for value in node.args.kw_defaults if value is not None]
        + ([node.returns] if node.returns is not None else [])
    )
    for expression in outer_expressions:
        error = _check_expr(
            expression,
            available,
            cleared_apis,
            allow_unknown=allow_unknown,
        )
        if error:
            return error

    locals_ = _function_locals(node)
    error, _ = _check_block(
        node.body,
        available | locals_ | {node.name},
        cleared_apis,
        allow_unknown=allow_unknown,
        function_scope=True,
    )
    return error


def _check_target(
    target: ast.AST,
    available: set[str],
    cleared_apis: set[int],
    *,
    allow_unknown: bool,
) -> str | None:
    if isinstance(target, (ast.Name, ast.Tuple, ast.List)):
        for child in ast.iter_child_nodes(target):
            error = _check_target(
                child,
                available,
                cleared_apis,
                allow_unknown=allow_unknown,
            )
            if error:
                return error
        return None
    return _check_expr(
        target,
        available,
        cleared_apis,
        allow_unknown=allow_unknown,
    )


def _check_block(
    body: list[ast.stmt],
    initial: set[str],
    cleared_apis: set[int],
    *,
    allow_unknown: bool,
    function_scope: bool = False,
) -> tuple[str | None, set[str]]:
    """Check a statement block and return names bound on every successful path."""
    available = set(initial)
    for stmt in body:
        error: str | None = None

        if isinstance(stmt, ast.Expr):
            error = _check_expr(
                stmt.value,
                available,
                cleared_apis,
                allow_unknown=allow_unknown,
            )
        elif isinstance(stmt, ast.Assign):
            error = _check_expr(
                stmt.value,
                available,
                cleared_apis,
                allow_unknown=allow_unknown,
            )
            if not error:
                for target in stmt.targets:
                    error = _check_target(
                        target,
                        available,
                        cleared_apis,
                        allow_unknown=allow_unknown,
                    )
                    if error:
                        break
            if not error:
                for target in stmt.targets:
                    available |= _target_names(target)
        elif isinstance(stmt, ast.AnnAssign):
            error = _check_expr(
                stmt.annotation,
                available,
                cleared_apis,
                allow_unknown=allow_unknown,
            )
            if not error:
                error = _check_expr(
                    stmt.value,
                    available,
                    cleared_apis,
                    allow_unknown=allow_unknown,
                )
            if not error and stmt.value is not None:
                available |= _target_names(stmt.target)
        elif isinstance(stmt, ast.AugAssign):
            if isinstance(stmt.target, ast.Name) and stmt.target.id not in available:
                error = _name_error(
                    ast.Name(id=stmt.target.id, ctx=ast.Load()),
                    available,
                    cleared_apis,
                    allow_unknown=allow_unknown,
                )
            if not error:
                error = _check_target(
                    stmt.target,
                    available,
                    cleared_apis,
                    allow_unknown=allow_unknown,
                )
            if not error:
                error = _check_expr(
                    stmt.value,
                    available,
                    cleared_apis,
                    allow_unknown=allow_unknown,
                )
            if not error:
                available |= _target_names(stmt.target)
        elif isinstance(stmt, ast.Import):
            available |= {
                alias.asname or alias.name.split(".")[0] for alias in stmt.names
            }
        elif isinstance(stmt, ast.ImportFrom):
            available |= {alias.asname or alias.name for alias in stmt.names}
        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            error = _check_function(
                stmt,
                available,
                cleared_apis,
                allow_unknown=allow_unknown,
            )
            if not error:
                available.add(stmt.name)
        elif isinstance(stmt, ast.ClassDef):
            for expression in (
                list(stmt.decorator_list)
                + list(stmt.bases)
                + [keyword.value for keyword in stmt.keywords]
            ):
                error = _check_expr(
                    expression,
                    available,
                    cleared_apis,
                    allow_unknown=allow_unknown,
                )
                if error:
                    break
            if not error:
                error, _ = _check_block(
                    stmt.body,
                    available,
                    cleared_apis,
                    allow_unknown=allow_unknown,
                )
            if not error:
                available.add(stmt.name)
        elif isinstance(stmt, ast.If):
            body_after = set(available)
            else_after = set(available)
            error = _check_expr(
                stmt.test,
                available,
                cleared_apis,
                allow_unknown=allow_unknown,
            )
            if not error:
                error, body_after = _check_block(
                    stmt.body,
                    available,
                    cleared_apis,
                    allow_unknown=allow_unknown,
                    function_scope=function_scope,
                )
            if not error:
                if stmt.orelse:
                    error, else_after = _check_block(
                        stmt.orelse,
                        available,
                        cleared_apis,
                        allow_unknown=allow_unknown,
                        function_scope=function_scope,
                    )
                else:
                    else_after = set(available)
            if not error:
                available = body_after & else_after
        elif isinstance(stmt, (ast.For, ast.AsyncFor)):
            error = _check_expr(
                stmt.iter,
                available,
                cleared_apis,
                allow_unknown=allow_unknown,
            )
            if not error:
                error, _ = _check_block(
                    stmt.body,
                    available | _target_names(stmt.target),
                    cleared_apis,
                    allow_unknown=allow_unknown,
                    function_scope=function_scope,
                )
            if not error:
                error, _ = _check_block(
                    stmt.orelse,
                    available,
                    cleared_apis,
                    allow_unknown=allow_unknown,
                    function_scope=function_scope,
                )
        elif isinstance(stmt, ast.While):
            error = _check_expr(
                stmt.test,
                available,
                cleared_apis,
                allow_unknown=allow_unknown,
            )
            if not error:
                error, _ = _check_block(
                    stmt.body,
                    available,
                    cleared_apis,
                    allow_unknown=allow_unknown,
                    function_scope=function_scope,
                )
            if not error:
                error, _ = _check_block(
                    stmt.orelse,
                    available,
                    cleared_apis,
                    allow_unknown=allow_unknown,
                    function_scope=function_scope,
                )
        elif isinstance(stmt, (ast.With, ast.AsyncWith)):
            inner = set(available)
            for item in stmt.items:
                error = _check_expr(
                    item.context_expr,
                    inner,
                    cleared_apis,
                    allow_unknown=allow_unknown,
                )
                if error:
                    break
                if item.optional_vars is not None:
                    inner |= _target_names(item.optional_vars)
            if not error:
                error, _ = _check_block(
                    stmt.body,
                    inner,
                    cleared_apis,
                    allow_unknown=allow_unknown,
                    function_scope=function_scope,
                )
            if not error:
                available = inner
        elif isinstance(stmt, ast.Try):
            error, _ = _check_block(
                stmt.body,
                available,
                cleared_apis,
                allow_unknown=allow_unknown,
                function_scope=function_scope,
            )
            for handler in stmt.handlers:
                if error:
                    break
                error = _check_expr(
                    handler.type,
                    available,
                    cleared_apis,
                    allow_unknown=allow_unknown,
                )
                if not error:
                    handler_available = set(available)
                    if handler.name:
                        handler_available.add(handler.name)
                    error, _ = _check_block(
                        handler.body,
                        handler_available,
                        cleared_apis,
                        allow_unknown=allow_unknown,
                        function_scope=function_scope,
                    )
            if not error:
                error, _ = _check_block(
                    stmt.orelse,
                    available,
                    cleared_apis,
                    allow_unknown=allow_unknown,
                    function_scope=function_scope,
                )
            if not error:
                error, available = _check_block(
                    stmt.finalbody,
                    available,
                    cleared_apis,
                    allow_unknown=allow_unknown,
                    function_scope=function_scope,
                )
        elif isinstance(stmt, ast.Assert):
            error = _check_expr(
                stmt.test,
                available,
                cleared_apis,
                allow_unknown=allow_unknown,
            ) or _check_expr(
                stmt.msg,
                available,
                cleared_apis,
                allow_unknown=allow_unknown,
            )
        elif isinstance(stmt, (ast.Return, ast.Raise)):
            error = _check_expr(
                getattr(stmt, "value", None) or getattr(stmt, "exc", None),
                available,
                cleared_apis,
                allow_unknown=allow_unknown,
            )
            if not error and isinstance(stmt, ast.Raise):
                error = _check_expr(
                    stmt.cause,
                    available,
                    cleared_apis,
                    allow_unknown=allow_unknown,
                )
        elif isinstance(stmt, ast.Delete):
            for target in stmt.targets:
                available -= _target_names(target)
        elif isinstance(stmt, (ast.Pass, ast.Break, ast.Continue)):
            pass
        else:
            error = (
                None
                if allow_unknown
                else f"the statement {type(stmt).__name__!r} is not permitted."
            )

        if error:
            return error, available

    return None, available


def bound_names(code: str) -> set[str]:
    """Names guaranteed to exist after a successful turn.

    AppWorld's shell persists across `execute()` calls, so this is not bookkeeping
    -- it is the difference between a gate that works and one that refuses a
    specialist the token it logged in with two turns ago.

    "Guaranteed" is load-bearing: a loop may run zero times, an ``if`` may take
    either branch, and a nested scope does not bind its parameters in the module.
    Carrying any of those names would let a later turn fall through to a name
    supplied by AppWorld instead.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return set()
    _, available = _check_block(
        tree.body,
        set(),
        set(),
        allow_unknown=True,
    )
    return available


def inspect_code(code: str, app: str | Iterable[str],
                 known: Iterable[str] = ()) -> str | None:
    """Why `code` may not run for an agent holding `app`, or None if it may.

    `app` is one app name, or several: the OPEN control is a single agent holding
    the whole roster, and it is the ruler every partitioned score is read
    against. A gate that refused the control's own APIs would sink the control to
    the floor and make the partition look like a triumph.

    `known` is what the specialist bound on earlier turns. The shell is stateful,
    so a name assigned on turn 3 is a free name on turn 4 and refusing it is a
    false positive -- observed live, refusing `access_token=access_token` on a
    correct brief. Nothing forbidden can arrive this way: a name only enters
    `known` by surviving this same gate.

    The reason is returned to the specialist verbatim in place of the execution
    output, so it is phrased for the model that has to correct itself.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        # Not waved through. IPython escapes (`!cmd`, `%magic`) are not valid
        # Python but ARE executable by run_cell; only AppWorld's own ast.parse
        # currently stops them, and that is its ordering to change, not ours.
        return ("that is not valid Python. Send a plain fenced python block -- "
                "shell escapes (`!`) and IPython magics (`%`) are not available.")

    held = {app} if isinstance(app, str) else set(app)
    allowed_apps = held | set(_SHARED_APPS)

    # `apis` is legitimate only as the direct base of `apis.<allowed>`. Clear
    # those occurrences first; every other mention is then a bypass attempt --
    # `a = apis`, `f(apis)`, `getattr(apis, 'phone')` -- and is refused below.
    cleared: set[int] = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "apis"):
            if node.attr not in allowed_apps:
                return (f"apis.{node.attr} belongs to another specialist. You may "
                        f"use only: {', '.join(sorted(allowed_apps))}.")
            cleared.add(id(node.value))

    borrowable = _ALLOWED_IMPORTS | _ALLOWED_BUILTINS

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root not in _ALLOWED_IMPORTS:
                    return f"importing {root!r} is not permitted."
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root not in _ALLOWED_IMPORTS:
                return f"importing from {root!r} is not permitted."
            # ... and not a module *out* of a permitted one. `from uuid import
            # os` binds the banned module as a first-class name, which
            # `_bound_names` would then count as the code's own.
            for alias in node.names:
                if alias.name in _module_attrs(root):
                    return (f"{root}.{alias.name} is the {alias.name!r} module; "
                            f"importing it is not permitted.")
        elif isinstance(node, ast.Attribute):
            # Blocks the object-graph walk: ().__class__.__bases__[0]...
            if node.attr.startswith("__"):
                return f"attribute {node.attr!r} is not permitted."
            # An allowlisted module's module-valued attributes are the banned
            # modules wearing another name: `uuid.os.environ`, `pprint._sys.
            # modules[...]`. The import ban is default-deny; without this the
            # attribute check was a denylist of exactly one pattern (`__*`),
            # which is the argument this module's docstring makes against
            # denylists, applied to itself.
            if (isinstance(node.value, ast.Name)
                    and node.value.id in _ALLOWED_IMPORTS
                    and node.attr in _module_attrs(node.value.id)):
                return (f"{node.value.id}.{node.attr} is the {node.attr!r} "
                        f"module, which is not permitted. Import the standard "
                        f"library modules you need by name.")
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            return (
                "global and nonlocal declarations are not permitted; keep "
                "specialist state in ordinary variables."
            )

    error, _ = _check_block(
        tree.body,
        set(known) | set(borrowable),
        cleared,
        allow_unknown=False,
    )
    return error
