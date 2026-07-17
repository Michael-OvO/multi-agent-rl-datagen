"""The environment you measure in must be the environment you ship.

`pyproject.toml` and `container/Dockerfile.sidecar` install AppWorld twice: once
for the sweep that produces every number in WRITEUP.md, once for the container a
reviewer actually runs. Nothing forces them to agree, and if they drift the sweep
measures a different AppWorld than the shipped task -- silently, and in exactly
the way §7 is a catalogue of.

It is also not hypothetical for this repo specifically: `sandbox.py` is written
against appworld 0.1.3's internals. It assumes `world.execute()` runs in-process,
that the shell is an `InteractiveShellEmbed` (hence `get_ipython`), and that
`requester` is bound in the namespace. A version bump can move any of those.
"""

import re
import tomllib
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_PYPROJECT = _ROOT / "pyproject.toml"
_SIDECAR = _ROOT / "forge" / "appworld" / "container" / "Dockerfile.sidecar"


def _sidecar_pins() -> dict[str, str]:
    """What the container installs, read out of its own pip line."""
    line = next(ln for ln in _SIDECAR.read_text().splitlines()
                if "pip install" in ln)
    return dict(re.findall(r"([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+-]+)", line))


def _declared_pins() -> dict[str, str]:
    data = tomllib.loads(_PYPROJECT.read_text())
    return dict(re.findall(r"([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+-]+)",
                           " ".join(data["project"]["dependencies"])))


def test_the_sidecar_pins_every_package_it_installs():
    pins = _sidecar_pins()
    assert set(pins) == {"appworld", "openai"}, (
        f"the sidecar installs something unpinned or unexpected: {pins}"
    )


@pytest.mark.parametrize("package", ["appworld", "openai"])
def test_the_declared_environment_matches_the_container(package):
    declared, shipped = _declared_pins(), _sidecar_pins()
    assert declared.get(package) == shipped.get(package), (
        f"{package}: pyproject.toml pins {declared.get(package)}, the sidecar "
        f"installs {shipped.get(package)}. The sweep would measure one AppWorld "
        f"and the shipped task would run another."
    )


@pytest.mark.parametrize("package", ["appworld", "openai"])
def test_the_installed_environment_matches_what_is_declared(package):
    """What is actually importable, not what a file says.

    This repo's environment was assembled by hand for a while: `appworld` was
    installed in the venv, `openai` was not, and neither was declared anywhere.
    The sweep ran against a different interpreter than the tests. That works
    until someone else clones it.
    """
    import importlib.metadata as md

    try:
        installed = md.version(package)
    except md.PackageNotFoundError:
        pytest.fail(
            f"{package} is declared in pyproject.toml but not installed in this "
            f"interpreter. Run `uv sync` (or `pip install -e .`) -- do not reach "
            f"for another Python that happens to have it."
        )
    assert installed == _declared_pins()[package], (
        f"{package}: {installed} installed, pyproject.toml pins "
        f"{_declared_pins()[package]}"
    )


def test_appworld_data_is_reachable_from_the_repo_root():
    """AppWorld resolves its dataset relative to APPWORLD_ROOT.

    The repo keeps a `data -> appworld_data` symlink so `APPWORLD_ROOT=$PWD`
    works from the root. Without the data, every probe fails deep inside AppWorld
    with something unhelpful; this says so in one line instead.
    """
    data = _ROOT / "data"
    if not data.exists():
        pytest.skip("no appworld dataset locally (run: appworld download data)")
    assert (data / "tasks").exists() or (data / "base").exists(), (
        f"{data} exists but does not look like the AppWorld dataset"
    )


def test_every_entry_point_that_imports_appworld_hardens_the_root_first():
    """`_env.ensure_appworld_root()` before `import appworld`, everywhere.

    AppWorld resolves its dataset relative to APPWORLD_ROOT, so an entry point
    that skips this works from the repo root and dies anywhere else, deep inside
    a dependency, with a message about a path nobody wrote. That is the whole
    reason `scripts/_env.py` exists.

    It was a rule six of seven callers followed. The seventh was
    `forge/appworld/cli.py` -- the module README calls "the pipeline" -- and
    nothing noticed, because pytest and every documented command already start
    in the right directory. A convention that only one file breaks is a
    convention nothing is enforcing.
    """
    import ast

    root = Path(__file__).resolve().parents[2]
    entry_points = sorted((root / "scripts").glob("appworld_*.py"))
    entry_points += [root / "scripts" / "watch_episode.py",
                     root / "forge" / "appworld" / "cli.py"]

    offenders = []
    for path in entry_points:
        text = path.read_text()
        tree = ast.parse(text)
        imports_appworld = any(
            (isinstance(n, ast.ImportFrom) and (n.module or "").split(".")[0] == "appworld")
            or (isinstance(n, ast.Import)
                and any(a.name.split(".")[0] == "appworld" for a in n.names))
            for n in ast.walk(tree)
        )
        if imports_appworld and "ensure_appworld_root()" not in text:
            offenders.append(path.relative_to(root).as_posix())

    assert not offenders, (
        f"these import appworld without pointing it at the dataset first: "
        f"{offenders}; call scripts._env.ensure_appworld_root() before the import"
    )
