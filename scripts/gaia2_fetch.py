"""Fetch the Gaia2 `mini` split and unpack it to one JSON file per scenario.

Gaia2 (Meta ARE, ICLR 2026) ships as parquet on Hugging Face. The forge's
miner works on plain scenario dicts, so this script is the only place parquet
is touched -- and therefore the only place pyarrow is needed. It is *not* a
project dependency (pyproject pins are exactly the sidecar's environment);
run this with the deps supplied ad hoc:

    uv run --with pandas --with pyarrow python -m scripts.gaia2_fetch

Output: gaia2_data/mini/<scenario_id>.json (gitignored, ~160 files), and the
download is skipped when the files are already there.
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

URL = (
    "https://huggingface.co/datasets/meta-agents-research-environments/gaia2/"
    "resolve/main/mini/validation-00000-of-00001.parquet"
)
PARQUET = Path("gaia2_data/gaia2_mini.parquet")
OUT_DIR = Path("gaia2_data/mini")


def main() -> None:
    try:
        import pandas as pd  # pyright: ignore[reportMissingImports]
    except ImportError:
        raise SystemExit(
            "pandas/pyarrow are not project dependencies. Run:\n"
            "  uv run --with pandas --with pyarrow python -m scripts.gaia2_fetch"
        ) from None

    PARQUET.parent.mkdir(parents=True, exist_ok=True)
    if not PARQUET.exists():
        print(f"downloading {URL}")
        urllib.request.urlretrieve(URL, PARQUET)  # noqa: S310 -- fixed https URL
    print(f"parquet: {PARQUET} ({PARQUET.stat().st_size / 1e6:.1f} MB)")

    df = pd.read_parquet(PARQUET)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    for _, row in df.iterrows():
        scenario = json.loads(row["data"])
        # Keep the split's own labels next to the scenario: the admission
        # sweep reports per-category counts.
        scenario["_gaia2"] = {
            "id": row["id"],
            "scenario_id": row["scenario_id"],
            "category": row["category"],
        }
        out = OUT_DIR / f"{row['scenario_id']}.json"
        out.write_text(json.dumps(scenario))
        written += 1
    print(f"wrote {written} scenarios to {OUT_DIR}/")


if __name__ == "__main__":
    main()
