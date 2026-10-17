#!/usr/bin/env bash
# bottega-kit installer: copies the command into the data directory and links
# it onto PATH. Idempotent. Task data under <data>/tasks and the configuration
# under ~/.config/bottega-kit are never touched.
#
# Usage: ./install.sh
# Env overrides:
#   BOTTEGA_DATA_HOME  default ${XDG_DATA_HOME:-~/.local/share}/bottega-kit
#   BOTTEGA_BIN_HOME   default ~/.local/bin
# Set by `npx bottega-kit`, which installs from a temporary clone it deletes:
#   BOTTEGA_INSTALL_SOURCE  recorded as the source instead of this directory
#   BOTTEGA_INSTALL_REF     the tag or branch that was cloned
set -euo pipefail

KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_HOME="${BOTTEGA_DATA_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/bottega-kit}"
BIN_HOME="${BOTTEGA_BIN_HOME:-$HOME/.local/bin}"

case "${1:-}" in
  -h|--help) sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
  "") ;;
  *) echo "unknown argument: $1" >&2; exit 64 ;;
esac

command -v python3 >/dev/null 2>&1 || { echo "python3 is required" >&2; exit 69; }
python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))' \
  || { echo "python3 3.9 or newer is required" >&2; exit 69; }
command -v git >/dev/null 2>&1 || { echo "git is required" >&2; exit 69; }

mkdir -p "$DATA_HOME" "$BIN_HOME"
STAGE="$(mktemp -d "$DATA_HOME/.install.XXXXXX")"
trap 'rm -rf -- "$STAGE"' EXIT

# What ships: the command, its library, the templates (and the prompts, once
# they exist), and the licence files.
mkdir -p "$STAGE/bin/lib"
cp "$KIT/bin/bottega" "$STAGE/bin/bottega"
cp -R "$KIT/bin/lib/bottega" "$STAGE/bin/lib/bottega"
find "$STAGE" -name __pycache__ -prune -exec rm -rf {} +
cp -R "$KIT/templates" "$STAGE/templates"
[ ! -d "$KIT/prompts" ] || cp -R "$KIT/prompts" "$STAGE/prompts"
cp "$KIT/LICENSE" "$KIT/NOTICE" "$STAGE/"
chmod 755 "$STAGE/bin/bottega"

# Swap each shipped item in by rename. A running bottega keeps the modules it
# already imported; tasks/ is not in this list and is never touched.
for item in bin templates prompts LICENSE NOTICE; do
  rm -rf "${DATA_HOME:?}/$item.old"
  [ ! -e "$DATA_HOME/$item" ] || mv "$DATA_HOME/$item" "$DATA_HOME/$item.old"
  [ ! -e "$STAGE/$item" ] || mv "$STAGE/$item" "$DATA_HOME/$item"
  rm -rf "${DATA_HOME:?}/$item.old"
done
ln -sfn "$DATA_HOME/bin/bottega" "$BIN_HOME/bottega"
echo "bottega -> $BIN_HOME/bottega (installed under $DATA_HOME)"

# Written last, so the marker exists only if the install reached the end.
version="$(sed -n 's/^__version__ = "\([^"]*\)"$/\1/p' "$KIT/bin/lib/bottega/version.py")"
commit=""; dirty=false
if git -C "$KIT" rev-parse --git-dir >/dev/null 2>&1; then
  commit="$(git -C "$KIT" rev-parse HEAD 2>/dev/null || true)"
  [ -z "$(git -C "$KIT" status --porcelain 2>/dev/null)" ] || dirty=true
fi
python3 - "$DATA_HOME/installed-version.json" "$version" "$commit" "$dirty" \
  "${BOTTEGA_INSTALL_SOURCE:-$KIT}" "${BOTTEGA_INSTALL_REF:-}" <<'PY'
import datetime, json, os, sys, tempfile
path, version, commit, dirty, source, ref = sys.argv[1:]
marker = {
    "schema_version": 1,
    "version": version,
    "commit": commit or None,
    "commit_dirty": dirty == "true",
    "source": source,
    "ref": ref or None,
    "installed_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
}
fd, temp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".installed-version.")
with os.fdopen(fd, "w") as stream:
    json.dump(marker, stream, indent=2)
    stream.write("\n")
os.replace(temp, path)
PY
echo "installed bottega-kit $version$([ "$dirty" = true ] && echo ' (from a dirty checkout)')"

case ":$PATH:" in
  *":$BIN_HOME:"*) ;;
  *) echo "note: $BIN_HOME is not on PATH; add it to use bottega by name" ;;
esac
echo "next: bottega init, then bottega doctor"
