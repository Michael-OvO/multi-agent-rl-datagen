"""How big an app's API catalog is, and what truncating it destroys.

`run_specialist` fed execution output back to the specialist through
`str(result)[:2500]`. The comment said the cap was there to survive the TPM
ceiling, which was true. What it did *not* say is that the first thing every
specialist executes is `apis.api_docs.show_api_descriptions(app_name=...)` --
the API catalog -- and that `venmo`'s catalog is 5,444 characters.

So the cap cut the catalog in half, mid-JSON, with no marker. 30 of venmo's 54
APIs vanished, including **`like_transaction`** and **`show_social_feed`** -- the
two APIs the shipped tasks are entirely about ("Like all the venmo transactions
... on my venmo social feed"). The specialist was ordered not to guess API names
and then shown a list that did not contain the one it needed.

This is what the 0.333 was. Not "the partition is hard" -- the specialist could
not find the verb.

    APPWORLD_ROOT=$PWD python -m scripts.appworld_catalog_probe

Measured 2026-07-15. No LLM involved; this is a property of the catalog and an
integer.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

#: The apps the shipped tasks actually use. See forge/appworld/reference.py.
APPS = ("phone", "venmo")

#: The cap that was in place when every number in WRITEUP.md §5 was measured.
OLD_CAP = 2500

OUT = Path("sweep/appworld_api_catalog.json")

#: APIs without which the shipped tasks cannot be completed at all.
LOAD_BEARING = {"venmo": ("like_transaction", "show_social_feed")}


def main() -> None:
    from appworld import AppWorld

    rows = []
    with AppWorld(task_id="2a163ab_1", experiment_name="catalog_probe",
                  ground_truth_mode="minimal") as world:
        for app in APPS:
            text = str(world.execute(
                f"print(apis.api_docs.show_api_descriptions(app_name={app!r}))"))
            names = re.findall(r'"name": "(\w+)"', text)
            survived = re.findall(r'"name": "(\w+)"', text[:OLD_CAP])
            lost = [n for n in names if n not in survived]

            rows.append({
                "app": app,
                "catalog_chars": len(text),
                "apis_total": len(names),
                "apis_visible_under_old_cap": len(survived),
                "apis_lost_to_old_cap": lost,
                "load_bearing_apis_lost": sorted(
                    set(LOAD_BEARING.get(app, ())) & set(lost)),
            })
            print(f"{app}: {len(text)} chars, {len(names)} APIs, "
                  f"{len(lost)} lost to the {OLD_CAP} cap")
            if rows[-1]["load_bearing_apis_lost"]:
                print(f"  TASK-CRITICAL APIS LOST: {rows[-1]['load_bearing_apis_lost']}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, indent=1))
    print(f"\nwrote {OUT}")
    print(f"largest catalog: {max(r['catalog_chars'] for r in rows)} chars -- any "
          f"cap below this silently deletes APIs")


if __name__ == "__main__":
    main()
