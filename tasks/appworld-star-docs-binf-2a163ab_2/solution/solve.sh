#!/bin/bash
# No planted solution. The oracle is AppWorld's state check, and the
# reference path is a real orchestration -- there is nothing to replay.
echo 'appworld tasks have no planted oracle by design' >&2
exit 1
