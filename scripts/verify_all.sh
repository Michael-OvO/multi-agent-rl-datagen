#!/usr/bin/env bash
# Verify every generated sample task with Harbor's oracle agent (needs Docker).
# Each task must report reward 1.0.
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"

tasks=(tasks/parallel-scheduling-* tasks/failure-recovery-* tasks/theory-of-mind-*)
for t in "${tasks[@]}"; do
  echo "==================== oracle: $t ===================="
  harbor run --path "$t" --agent oracle -n 1
done
echo "All oracle runs complete. Inspect rewards above (expect 1.0 each)."
