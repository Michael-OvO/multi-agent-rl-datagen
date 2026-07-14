#!/bin/bash
set -e
python3 - <<'PY'
import json, sys
sys.path.insert(0, '/app/lib')
import maf_dim
inst = json.load(open('/opt/maf/scenario.json'))
tr = maf_dim.run_policy(inst, maf_dim.ORACLE)
with open('/app/transcript.jsonl', 'w') as fh:
    for x in tr:
        fh.write(json.dumps(x) + '\n')
PY
