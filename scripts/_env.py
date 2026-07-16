"""Make `python -m scripts.<anything>` work from the repo root.

AppWorld resolves its dataset relative to `APPWORLD_ROOT`, and this repo keeps a
`data -> appworld_data` symlink at its root. Every probe therefore needs
`APPWORLD_ROOT=$PWD`, and forgetting it produces a failure deep inside AppWorld
that says nothing about the actual cause.

So the entry points set it themselves, and say something useful when the dataset
is not there at all. An explicit default in the five scripts that need it, not an
import side effect in the library.
"""

from __future__ import annotations

import os
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def ensure_appworld_root() -> None:
    """Point AppWorld at this repo's dataset. Call before importing appworld."""
    os.environ.setdefault("APPWORLD_ROOT", str(_ROOT))

    data = Path(os.environ["APPWORLD_ROOT"]) / "data"
    if not data.exists():
        raise SystemExit(
            f"No AppWorld dataset at {data}.\n"
            f"  uv run appworld install\n"
            f"  uv run appworld download data\n"
            f"(`appworld install` is required again after any reinstall of the "
            f"package -- it unpacks the app source, and `uv sync` wipes it.)"
        )


def require_api_key() -> None:
    """The specialists are real LLMs; anything that runs one needs a key."""
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit(
            "OPENAI_API_KEY not set. Try:  set -a && . ./.env && set +a"
        )
