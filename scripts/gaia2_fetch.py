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

import argparse
import json
import urllib.request
from pathlib import Path

#: The dataset's parquet folders. `mini` is the 160-scenario balanced subset;
#: the five capability splits are the full validation set.
SPLITS = ("mini", "adaptability", "ambiguity", "execution", "search", "time")


def _url(split: str) -> str:
    return (
        "https://huggingface.co/datasets/meta-agents-research-environments/gaia2/"
        f"resolve/main/{split}/validation-00000-of-00001.parquet"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=SPLITS, default="mini")
    args = parser.parse_args()
    split = args.split
    parquet = Path(f"gaia2_data/gaia2_{split}.parquet")
    out_dir = Path(f"gaia2_data/{split}")
    try:
        import pandas as pd  # pyright: ignore[reportMissingImports]
    except ImportError:
        raise SystemExit(
            "pandas/pyarrow are not project dependencies. Run:\n"
            "  uv run --with pandas --with pyarrow python -m scripts.gaia2_fetch"
        ) from None

    parquet.parent.mkdir(parents=True, exist_ok=True)
    if not parquet.exists():
        url = _url(split)
        print(f"downloading {url}")
        urllib.request.urlretrieve(url, parquet)  # noqa: S310 -- fixed https URL
    print(f"parquet: {parquet} ({parquet.stat().st_size / 1e6:.1f} MB)")

    df = pd.read_parquet(parquet)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for _, row in df.iterrows():
        scenario = json.loads(row["data"])
        # Keep the split's own labels next to the scenario: the admission
        # sweep reports per-category counts.
        scenario["_gaia2"] = {
            "id": row["id"],
            "scenario_id": row["scenario_id"],
            # `mini` carries a category column; the five capability splits
            # drop it because the split name *is* the category.
            "category": row["category"] if "category" in df.columns else split,
            "split": split,
        }
        out = out_dir / f"{row['scenario_id']}.json"
        out.write_text(json.dumps(scenario))
        written += 1
    print(f"wrote {written} scenarios to {out_dir}/")


if __name__ == "__main__":
    main()
