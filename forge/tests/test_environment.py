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

import json
import re
import subprocess
import tomllib
from pathlib import Path

import pytest
from packaging.requirements import Requirement

_ROOT = Path(__file__).resolve().parents[2]
_PYPROJECT = _ROOT / "pyproject.toml"
_SIDECAR = _ROOT / "forge" / "appworld" / "container" / "Dockerfile.sidecar"

_GAIA2_IN = _ROOT / "requirements-gaia2.in"
_GAIA2_REQS = _ROOT / "requirements-gaia2.txt"
_GAIA2_SIDECAR = _ROOT / "forge" / "gaia2" / "container" / "Dockerfile.sidecar"
_GAIA2_VENV = _ROOT / ".venv-gaia2"
_PYTHON_VERSION = _ROOT / ".python-version"


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


# --- Gaia2 -----------------------------------------------------------------
#
# Everything above guards AppWorld, which is the substrate this repo retired.
# Gaia2 produces every number now, and for a while it had no guard at all: the
# local `.venv-gaia2` was two imperative lines in the README, the sidecar
# repeated the same two pins by hand, and nothing compared them. That is the
# drift this file's opening paragraph is about, aimed at the live substrate.
#
# The fix is structural rather than assertive. There is one pin file,
# `requirements-gaia2.txt`; the local environment installs from it, and the
# sidecar installs from a verbatim copy of it that `harbor.VERBATIM_COPIES`
# ships into every rendered task. Two lists cannot disagree when there is one
# list. What remains testable is that nobody reintroduces a second one.


def _normalize(name: str) -> str:
    """PEP 503 name folding: `Meta_Agents.Research` and `meta-agents-research`
    are the same project, and dist-info spells it differently than pip freeze."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _requirement_pins(path: Path) -> dict[str, str]:
    """Every `name==version` in a requirements file, ignoring comments.

    `uv pip compile` annotates each pin with an indented `# via ...` line and
    heads the file with the command that regenerates it; neither is a pin.
    """
    pins = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", "-")):
            continue
        name, _, version = line.partition("==")
        pins[_normalize(name)] = version.split()[0] if version else ""
    return pins


def _target_environment(venv: Path) -> dict[str, str]:
    """The marker variables a requirement is evaluated against for `venv`.

    Asked of the target interpreter rather than reconstructed around it. The
    previous version read `version_info` out of pyvenv.cfg, which uv writes as
    `3.11` -- two components -- and invented `python_full_version = 3.11.0` for
    an interpreter that is actually 3.11.15. No marker in the current file reads
    that variable, so nothing was mis-evaluated yet; a future `python_full_version`
    marker would have been, silently and in the lenient direction.

    Built from the stdlib in the target process, not from `packaging`: that is
    a transitive dependency of the very file under test, and a guard should not
    stop working because a recompile dropped one of its own subjects.
    """
    probe = (
        "import json, os, platform, sys;"
        "v = sys.implementation.version;"
        "iv = '{0.major}.{0.minor}.{0.micro}'.format(v) +"
        "     ('' if v.releaselevel == 'final' else v.releaselevel[0] + str(v.serial));"
        "print(json.dumps({"
        "  'implementation_name': sys.implementation.name,"
        "  'implementation_version': iv,"
        "  'os_name': os.name,"
        "  'platform_machine': platform.machine(),"
        "  'platform_release': platform.release(),"
        "  'platform_system': platform.system(),"
        "  'platform_version': platform.version(),"
        "  'python_full_version': platform.python_version(),"
        "  'platform_python_implementation': platform.python_implementation(),"
        "  'python_version': '.'.join(platform.python_version_tuple()[:2]),"
        "  'sys_platform': sys.platform,"
        "}))"
    )
    result = subprocess.run([venv / "bin" / "python", "-c", probe],
                            capture_output=True, text=True)
    assert result.returncode == 0, (
        f"could not read the marker environment from {venv.name}: "
        f"{result.stderr.strip()}"
    )
    return {key: str(value) for key, value in json.loads(result.stdout).items()}


def _applicable_pins(path: Path, env: dict[str, str]) -> dict[str, str]:
    """Declared pins whose marker actually holds for `env`.

    The file is resolved `--universal` so one list serves macos/arm64 locally
    and linux/amd64 in the sidecar, which means a declared pin is not always an
    installed pin. The first version of this check treated *every* marker-bearing
    pin as optional, which is far too coarse: of the six markers in this file
    only `colorama` and `pywin32` are win32-gated, while `cffi`, `hf-xet`,
    `pycparser` and `uvicorn` are live here. Any of those four could vanish from
    the environment and be reported as legitimately absent. Markers get
    evaluated, not waved through.
    """
    applicable = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", "-")):
            continue
        req = Requirement(line)
        if req.marker is not None and not req.marker.evaluate(env):
            continue
        version = next((s.version for s in req.specifier if s.operator == "=="), "")
        applicable[_normalize(req.name)] = version
    return applicable


def _installed_in(venv: Path) -> dict[str, str]:
    """What is actually importable in a virtualenv, read off its dist-info.

    Deliberately not `importlib.metadata` against the *current* interpreter:
    the suite runs under `.venv`, and the environment worth checking is the
    other one. A test that only fires when you remember to run it under the
    right Python is a test that never fires.
    """
    site = next(venv.glob("lib/python*/site-packages"), None)
    if site is None:
        return {}
    installed = {}
    for d in site.glob("*.dist-info"):
        name, _, version = d.name.removesuffix(".dist-info").rpartition("-")
        installed[_normalize(name)] = version
    return installed


_needs_gaia2_venv = pytest.mark.skipif(
    not _GAIA2_VENV.exists(),
    reason="no .venv-gaia2 locally (see README: uv venv .venv-gaia2)",
)


def test_the_gaia2_requirements_pin_every_package_exactly():
    """A floor or a range is not a measurement environment.

    `>=` here would mean the episodes in output/rollouts/ were taken under a
    resolution nothing recorded, which is the whole failure this file exists
    to prevent -- transitively, not just for the two packages named by hand.
    """
    pins = _requirement_pins(_GAIA2_REQS)
    assert pins, f"{_GAIA2_REQS.name} declares no pins"
    unpinned = sorted(name for name, version in pins.items() if not version)
    assert not unpinned, (
        f"{_GAIA2_REQS.name} does not pin an exact version for: {unpinned}"
    )


def test_the_gaia2_intent_file_names_only_what_this_environment_is_for():
    """The `.in` file is the statement of intent; the `.txt` is its closure.

    Two packages: the official harness, and the client the specialists and the
    judge speak to. Everything else in the compiled file is a consequence, and
    should never be edited by hand.
    """
    direct = _requirement_pins(_GAIA2_IN)
    assert set(direct) == {"meta-agents-research-environments", "openai"}, (
        f"{_GAIA2_IN.name} declares {sorted(direct)}; this environment exists "
        f"for the Gaia2 harness and its model client, and nothing else belongs "
        f"in it -- add it to pyproject.toml instead"
    )
    compiled = _requirement_pins(_GAIA2_REQS)
    for name, version in direct.items():
        assert compiled.get(name) == version, (
            f"{name}: {_GAIA2_IN.name} asks for {version}, "
            f"{_GAIA2_REQS.name} pins {compiled.get(name)} -- recompile with "
            f"`uv pip compile requirements-gaia2.in -o requirements-gaia2.txt`"
        )


def test_the_gaia2_sidecar_installs_from_the_committed_requirements():
    """The container and the measurement environment read the same file.

    Both halves are asserted, because either alone is satisfiable by a broken
    image. A `COPY requirements.txt` with no install puts the pin file in the
    image and installs nothing; an install with no COPY cannot find it. The
    first version of this test looked for the substring anywhere in the file,
    which the copy-only Dockerfile passes.
    """
    lines = [ln.strip() for ln in _GAIA2_SIDECAR.read_text().splitlines()]

    copied = [ln for ln in lines
              if ln.startswith("COPY") and "requirements.txt" in ln]
    assert copied, (
        f"{_GAIA2_SIDECAR.name} never COPYs requirements.txt into the image; "
        f"the install below it has nothing to read"
    )

    installs = [ln for ln in lines if re.search(
        r"pip\s+install\b.*(?:-r|--requirement)\s+\S*requirements\.txt", ln)]
    assert installs, (
        f"{_GAIA2_SIDECAR.name} does not `pip install -r requirements.txt`. "
        f"Copying the pin file into the image is not installing it -- the "
        f"sidecar would start with no harness at all"
    )


def test_the_gaia2_sidecar_declares_no_pin_of_its_own():
    """One list, not two that a test has to keep reconciling.

    The AppWorld pair above is guarded by comparing two hand-written pin lists.
    That works, and it is still one edit away from someone bumping a version in
    one place. Here the sidecar is not allowed to name a version at all.
    """
    install_lines = [
        ln for ln in _GAIA2_SIDECAR.read_text().splitlines()
        if "pip install" in ln
    ]
    inline = {pkg: ver for ln in install_lines
              for pkg, ver in re.findall(r"([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+-]+)", ln)}
    assert not inline, (
        f"{_GAIA2_SIDECAR.name} pins {inline} inline as well as installing the "
        f"requirements file; that is the second list this design removed"
    )


@_needs_gaia2_venv
def test_the_installed_gaia2_environment_matches_the_committed_requirements():
    """What is on disk, not what a file says it should be.

    `uv pip sync` makes these agree; anything installed by hand afterwards --
    a debugging `pip install`, a bumped judge client -- shows up here rather
    than in a trajectory nobody can reproduce.
    """
    declared = _requirement_pins(_GAIA2_REQS)
    applicable = _applicable_pins(_GAIA2_REQS, _target_environment(_GAIA2_VENV))
    installed = _installed_in(_GAIA2_VENV)
    assert installed, f"{_GAIA2_VENV.name} has no site-packages to check"
    resync = ("resync with `uv pip sync --python .venv-gaia2/bin/python "
              "requirements-gaia2.txt`")

    wrong_version = {
        name: (version, installed[name])
        for name, version in declared.items()
        if name in installed and installed[name] != version
    }
    assert not wrong_version, (
        f"{_GAIA2_VENV.name} has versions {_GAIA2_REQS.name} does not declare "
        f"(declared, installed): {wrong_version} -- {resync}"
    )

    missing = sorted(name for name in applicable if name not in installed)
    assert not missing, (
        f"{_GAIA2_REQS.name} declares these for this environment but "
        f"{_GAIA2_VENV.name} does not have them: {missing} -- {resync}"
    )

    # Against `applicable`, not `declared`: a pin whose marker excludes this
    # machine is not licence to have it installed. `colorama` and `pywin32` are
    # win32-gated, so on a Mac they are extras that `uv pip sync` would remove,
    # and subtracting the full universal declaration let them sit there
    # unnoticed -- the mirror image of the active-marker gap.
    undeclared = sorted(set(installed) - set(applicable))
    assert not undeclared, (
        f"{_GAIA2_VENV.name} carries packages {_GAIA2_REQS.name} does not "
        f"declare for this environment: {undeclared}. A hand-installed package "
        f"-- or one whose marker excludes this platform -- is exactly how an "
        f"episode becomes irreproducible; {resync}"
    )


def test_the_gaia2_environment_is_the_pydantic_2_one():
    """The reason this second environment exists, written down as a check.

    `are.simulation` needs pydantic 2; the main environment resolves pydantic 1
    under appworld. If a resolution ever brought them into line, the split would
    be pure overhead and this test should be deleted deliberately -- not
    discovered by an import error inside a paid episode.

    Deliberately *not* gated on `.venv-gaia2` existing: this reads the committed
    file, nothing else. Gating it meant a recompile that resolved pydantic 1
    would skip the guard everywhere the venv is absent -- CI, a fresh clone --
    which is exactly where nobody would notice.
    """
    pydantic = _requirement_pins(_GAIA2_REQS).get("pydantic", "")
    assert pydantic.startswith("2."), (
        f"requirements-gaia2.txt pins pydantic {pydantic!r}; the Gaia2 harness "
        f"needs 2.x, which is the entire reason .venv-gaia2 is separate"
    )


def test_the_pinned_interpreter_satisfies_the_declared_floor():
    """`requires-python` is a floor; `.python-version` is what you actually get.

    Without the pin, a fresh clone resolves `.venv` against whatever >=3.11 is
    on the machine while the README hard-codes 3.11 for `.venv-gaia2`, and the
    two environments quietly stop being the same Python.
    """
    pinned = _PYTHON_VERSION.read_text().strip()
    floor = tomllib.loads(_PYPROJECT.read_text())["project"]["requires-python"]
    assert pinned.startswith("3.11"), (
        f".python-version pins {pinned!r}, but the sidecars and .venv-gaia2 are "
        f"built on 3.11; they must be one interpreter"
    )
    assert floor == ">=3.11", (
        f"requires-python is {floor!r} but .python-version pins {pinned!r}"
    )
