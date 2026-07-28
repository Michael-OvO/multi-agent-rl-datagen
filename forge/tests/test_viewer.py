"""The viewer is one HTML file, so these are its contract tests.

`trajectory_viewer.html` has no build step and no unit-testable modules: its
CSS and JavaScript live inline. What can be checked here is the part that is
computable rather than visual -- that the loading model is the one the spec
approved, that every design token exists in all three theme scopes, and that
the colors clear WCAG contrast against the grounds they actually render on.
Node.js is not installed on the build machine, so the dataviz skill's palette
validator cannot run; this file carries the contrast math instead.

Layout, spacing, and "does it look right" are verified in a browser, not here.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_VIEWER = _ROOT / "trajectory_viewer.html"

#: Light and dark grounds a color may be painted on. Text must clear its
#: threshold against BOTH grounds of its own mode -- the plane is the darker
#: ground in light mode, the surface is the lighter one in dark mode.
_GROUNDS = {"light": ("#fcfcfb", "#f9f9f7"), "dark": ("#1a1a19", "#0d0d0d")}


@pytest.fixture(scope="module")
def viewer_html() -> str:
    return _VIEWER.read_text()


@pytest.fixture(scope="module")
def viewer_css(viewer_html: str) -> str:
    return re.search(r"<style>(.*?)</style>", viewer_html, re.S).group(1)


def _relative_luminance(hex_color: str) -> float:
    raw = hex_color.lstrip("#")
    channels = [int(raw[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
              for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a: str, b: str) -> float:
    """WCAG 2.x contrast ratio between two opaque hex colors."""
    hi, lo = sorted((_relative_luminance(a), _relative_luminance(b)),
                    reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def theme_scopes(css: str) -> dict[str, dict[str, str]]:
    """Token tables for the three scopes the viewer must define.

    'light' is the bare `:root` block; 'dark-os' is the one inside the
    prefers-color-scheme media query; 'dark-toggle' is the `data-theme`
    override. All three carry no nested braces, so a non-greedy match to the
    first `}` is exact.
    """
    scopes = {
        "light": r":root\s*\{(.*?)\}",
        "dark-os": r':root:not\(\[data-theme="light"\]\)\s*\{(.*?)\}',
        "dark-toggle": r':root\[data-theme="dark"\]\s*\{(.*?)\}',
    }
    out = {}
    for name, pattern in scopes.items():
        block = re.search(pattern, css, re.S)
        assert block, f"the {name} theme scope is missing from the stylesheet"
        out[name] = dict(re.findall(r"(--[a-z0-9-]+)\s*:\s*([^;]+);",
                                    block.group(1)))
    return out


#: Every identifier the File System Access layer was built from. The spec
#: retired that data source: the page carries its own snapshot, so opening
#: the file is the whole workflow and no permission prompt stands in front
#: of it.
_FOLDER_CONNECT_RELICS = [
    "showDirectoryPicker", "indexedDB", "queryPermission", "requestPermission",
    "openHandleDb", "connectRepository", "refreshRepository", "liveHandle",
    "folderpick", 'id="connect"', "DB_NAME", "webkitdirectory",
]


def test_the_folder_connect_layer_is_gone(viewer_html):
    """One loading model: the embedded snapshot, plus drop and pick."""
    body = viewer_html.split('<script type="application/json"')[0] \
        + viewer_html.split("</script>")[-1]
    survivors = [relic for relic in _FOLDER_CONNECT_RELICS if relic in body]
    assert not survivors, f"folder-connect machinery survives: {survivors}"


def test_the_snapshot_is_the_startup_path(viewer_html):
    assert "function loadSnapshot()" in viewer_html


def test_the_header_offers_exactly_two_actions(viewer_html):
    header = re.search(r"<header>(.*?)</header>", viewer_html, re.S)
    assert header, "the page header is missing"
    assert header.group(1).count("<button") + header.group(1).count("<label") == 2, (
        "the header's actions are 'open files' and 'theme' -- nothing else")


def test_embed_logs_block_still_matches_its_rewriter(viewer_html):
    """`scripts.embed_logs` rewrites the snapshot by regex; keep them agreed."""
    pattern = re.compile(
        r'(<script type="application/json" id="embedded-logs">).*?(</script>)',
        re.S)
    assert len(pattern.findall(viewer_html)) == 1
