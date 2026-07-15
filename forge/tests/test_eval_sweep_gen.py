"""The sweep generator bypasses `forge gen`, so it needs its own quarantine
and its own destructiveness pin.

It calls write_task directly, which means forge_cli's refusal to render a
quarantined dimension does not protect it -- verified: it hardcoded all three
dimensions and died with "only 0/2 passing seeds for failure-recovery/easy in
60 scans", *after* having already wiped sweep/instances at startup. It
destroyed the sweep set and could not rebuild it.
"""

import json
from pathlib import Path

import pytest

from forge.forge_cli import QUARANTINED
from scripts import eval_sweep_gen as esg


def test_end_to_end_run_generates_only_unquarantined_tasks(tmp_path, monkeypatch):
    # The real thing, no fakes: the whole generator runs in ~0.1s. On the
    # pre-fix script this died with SystemExit("only 0/2 passing seeds for
    # failure-recovery/easy in 60 scans"). A test that only asked whether a
    # helper filters a list would not have caught that -- the bug was that
    # main() rendered whatever DIMS said, and DIMS said all three.
    monkeypatch.chdir(tmp_path)
    esg.main()

    dirs = sorted(p.name for p in Path("sweep/instances").iterdir())
    assert dirs, "generated nothing at all"
    assert all(d.startswith("parallel-scheduling-") for d in dirs), dirs
    baselines = json.loads(Path("sweep/baselines.json").read_text())
    assert {v["dim"] for v in baselines.values()} == {"parallel-scheduling"}


def test_sweep_generator_skips_quarantined_dimensions():
    names = {d.NAME for d in esg.dimensions_to_generate()}
    assert names, "generator would render nothing at all"
    assert not (names & set(QUARANTINED)), (
        f"about to render quarantined dimensions: {names & set(QUARANTINED)}"
    )
    # Not vacuous: the one live dimension is still generated.
    assert "parallel-scheduling" in names


def test_failed_run_does_not_destroy_the_existing_instance_set(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    existing = Path("sweep/instances/parallel-scheduling-easy-0000")
    existing.mkdir(parents=True)
    (existing / "task.toml").write_text("from the previous good run")

    def _boom(out_dir):
        raise SystemExit("only 0/2 passing seeds for failure-recovery/easy")

    monkeypatch.setattr(esg, "_build", _boom)
    with pytest.raises(SystemExit):
        esg.main()

    # The whole point: a run that cannot succeed must leave the set it could
    # not rebuild exactly where it was.
    assert (existing / "task.toml").read_text() == "from the previous good run"
    leftovers = [p.name for p in Path("sweep").iterdir() if p.name.startswith(".")]
    assert leftovers == [], f"staging dirs left behind: {leftovers}"


def test_successful_run_replaces_the_instance_set(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    stale = Path("sweep/instances/parallel-scheduling-easy-9999")
    stale.mkdir(parents=True)
    (stale / "task.toml").write_text("stale instance from an older sweep")

    def _fake_build(out_dir):
        (out_dir / "parallel-scheduling-easy-0000").mkdir(parents=True)
        return {
            "parallel-scheduling-easy-0000": {
                "dim": "parallel-scheduling", "difficulty": "easy", "seed": 0,
                "oracle": 1.0, "cheaters": {"serial": 0.5}, "cheater_max": 0.5,
            }
        }

    monkeypatch.setattr(esg, "_build", _fake_build)
    esg.main()

    assert not stale.exists(), "stale instance survived a successful rebuild"
    assert Path("sweep/instances/parallel-scheduling-easy-0000").exists()
    assert "parallel-scheduling-easy-0000" in Path("sweep/baselines.json").read_text()
