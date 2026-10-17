#!/usr/bin/env bash
# bottega-kit doctor: is the installed command the one this checkout holds,
# and is this machine ready? The second question is `bottega doctor`'s.
#
# Usage: ./doctor.sh [--json]
#   --json  the installed-version section goes to stderr, the report to stdout
# Env overrides: BOTTEGA_DATA_HOME (as in install.sh)
set -uo pipefail

KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_HOME="${BOTTEGA_DATA_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/bottega-kit}"

json=0
for arg in "$@"; do
  case "$arg" in
    --json) json=1 ;;
    -h|--help) sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown argument: $arg" >&2; exit 64 ;;
  esac
done

failed=0
say() { if [ "$json" = 1 ]; then printf '%s\n' "$1" >&2; else printf '%s\n' "$1"; fi; }

say "Installed version"
marker="$DATA_HOME/installed-version.json"
kit_version="$(sed -n 's/^__version__ = "\([^"]*\)"$/\1/p' "$KIT/bin/lib/bottega/version.py")"
kit_commit="$(git -C "$KIT" rev-parse HEAD 2>/dev/null || true)"
if [ ! -f "$marker" ]; then
  say "  [FAIL] bottega-kit is not installed under $DATA_HOME; run ./install.sh"
  failed=1
else
  read_marker() { python3 -c 'import json,sys; v=json.load(open(sys.argv[1])).get(sys.argv[2]); print("" if v is None else v)' "$marker" "$1"; }
  inst_version="$(read_marker version)"
  inst_commit="$(read_marker commit)"
  if [ "$inst_version" != "$kit_version" ]; then
    say "  [FAIL] installed $inst_version but this checkout is $kit_version; run ./install.sh"
    failed=1
  else
    say "  [ OK ] installed version $inst_version matches this checkout"
  fi
  if [ -n "$kit_commit" ] && [ -n "$inst_commit" ] && [ "$inst_commit" != "$kit_commit" ]; then
    say "  [WARN] installed from commit ${inst_commit:0:8}, checkout is at ${kit_commit:0:8}; run ./install.sh to pick up the difference"
  fi
fi
[ "$json" = 1 ] || echo

"$KIT/bin/bottega" doctor "$@"
rc=$?
[ "$failed" = 0 ] || [ "$rc" != 0 ] || rc=2
exit "$rc"
