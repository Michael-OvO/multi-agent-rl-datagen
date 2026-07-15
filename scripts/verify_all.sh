#!/usr/bin/env bash
# Verify every generated sample task with Harbor's oracle agent (needs Docker).
# Each task must report reward 1.0.
#
# failure-recovery and theory-of-mind are quarantined (see
# forge/forge_cli.py:QUARANTINED) pending the Plan 2 sidecar -- their task
# dirs were deleted and forge_cli refuses to regenerate them, so only
# parallel-scheduling is globbed here.
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"

tasks=(tasks/parallel-scheduling-*)
for t in "${tasks[@]}"; do
  echo "==================== oracle: $t ===================="
  harbor run --path "$t" --agent oracle -n 1
done
echo "All oracle runs complete. Inspect rewards above (expect 1.0 each)."
