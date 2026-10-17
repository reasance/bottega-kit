#!/usr/bin/env bash
# Runs tests/harness-matrix.py in an isolated HOME, XDG and PATH (tests/lib/sandbox.sh).
set -euo pipefail
# shellcheck source=tests/lib/sandbox.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/sandbox.sh"
python3 "$ROOT/tests/harness-matrix.py"
