"""Refresh the optional fallback snapshot embedded in trajectory_viewer.html.

    uv run python -m scripts.embed_logs

The viewer normally reads the live repository through a remembered browser
directory handle, so new logs need no rebuild. A JSON snapshot remains useful
as a portable, zero-permission fallback or when sharing the HTML by itself.
This script rewrites that fallback from the current state of:

  * output/rollouts/*.json           -- Gaia2 episode trajectories
  * sweep/*.json                     -- measurement evidence
  * jobs/**/verifier/breakdown.json  -- shipped-task sidecar ledgers

You do not need to run this after new rollouts. Use it only when intentionally
refreshing the portable fallback.
"""

from __future__ import annotations

import datetime
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIEWER = ROOT / "trajectory_viewer.html"

#: One file larger than this is a mistake, not a log.
MAX_BYTES = 2_000_000

_BLOCK = re.compile(
    r'(<script type="application/json" id="embedded-logs">).*?(</script>)',
    re.S,
)


def snapshot() -> dict:
    files = []
    for pattern in ("output/rollouts/*.json", "sweep/*.json",
                    "jobs/**/verifier/breakdown.json"):
        for p in sorted(ROOT.glob(pattern)):
            if p.stat().st_size > MAX_BYTES:
                print(f"  skipping {p.relative_to(ROOT)} "
                      f"({p.stat().st_size / 1e6:.1f} MB)")
                continue
            files.append({"path": str(p.relative_to(ROOT)),
                          "data": json.loads(p.read_text())})
    return {
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "files": files,
    }


def main() -> None:
    snap = snapshot()
    # "</" must not appear literally inside a script element; the escaped
    # solidus is identical JSON.
    payload = json.dumps(snap, separators=(",", ":")).replace("</", "<\\/")
    html = VIEWER.read_text()
    # A function replacement, not a template: the payload is full of JSON
    # escapes ("…") that a template would try to interpret.
    new, n = _BLOCK.subn(lambda m: m.group(1) + payload + m.group(2), html)
    if n != 1:
        raise SystemExit("trajectory_viewer.html has no embedded-logs block; "
                         "the viewer and this script have drifted")
    VIEWER.write_text(new)
    print(f"embedded {len(snap['files'])} log files "
          f"({len(payload) / 1e3:.0f} kB) into {VIEWER.name}")


if __name__ == "__main__":
    main()
