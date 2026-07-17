"""The merge must refuse what it cannot tell apart.

A yield is a count over cells, so a merge that drops or double-counts a
replicate moves the number without moving anything a reader can see. These are
the two ways that happens.
"""

import json

import pytest

from scripts.merge_seeds import merge


def _row(task, config, seed, partial=1.0):
    return {"task_id": task, "config": config, "seed": seed, "partial": partial}


def _write(tmp_path, name, rows):
    p = tmp_path / name
    p.write_text(json.dumps(rows))
    return p


def test_replicates_from_separate_files_come_back_together(tmp_path):
    a = _write(tmp_path, "a.json", [_row("t", "star-docs-binf", 1, 1.0)])
    b = _write(tmp_path, "b.json", [_row("t", "star-docs-binf", 2, 0.833)])
    rows = merge([a, b])
    assert [r["partial"] for r in rows] == [1.0, 0.833]


def test_an_unlabelled_row_is_refused_rather_than_guessed(tmp_path):
    """Without a seed the merge cannot tell a replicate from a duplicate."""
    a = _write(tmp_path, "a.json", [{"task_id": "t", "config": "c", "partial": 1.0}])
    with pytest.raises(SystemExit, match="seed"):
        merge([a])


def test_the_same_replicate_twice_is_refused(tmp_path):
    """Re-running seed 2 into a new filename and merging both would count it
    twice -- and a doubled cell is a yield nobody can reproduce."""
    a = _write(tmp_path, "a.json", [_row("t", "star-docs-binf", 2, 1.0)])
    b = _write(tmp_path, "b.json", [_row("t", "star-docs-binf", 2, 0.333)])
    with pytest.raises(SystemExit, match="more than once"):
        merge([a, b])


def test_the_merge_is_ordered_so_two_runs_produce_the_same_file(tmp_path):
    a = _write(tmp_path, "a.json", [_row("t2", "star-docs-binf", 2)])
    b = _write(tmp_path, "b.json", [_row("t1", "star-docs-binf", 1)])
    assert merge([a, b]) == merge([b, a])
