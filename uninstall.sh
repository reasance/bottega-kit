#!/usr/bin/env bash
# bottega-kit uninstaller: removes what install.sh put in place. Keeps your
# tasks (<data>/tasks) and your configuration (~/.config/bottega-kit).
#
# Usage: ./uninstall.sh
# Env overrides: BOTTEGA_DATA_HOME, BOTTEGA_BIN_HOME (as in install.sh)
set -euo pipefail

DATA_HOME="${BOTTEGA_DATA_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/bottega-kit}"
BIN_HOME="${BOTTEGA_BIN_HOME:-$HOME/.local/bin}"

case "${1:-}" in
  -h|--help) sed -n '2,6p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
  "") ;;
  *) echo "unknown argument: $1" >&2; exit 64 ;;
esac

link="$BIN_HOME/bottega"
if [ -L "$link" ] && [ "$(readlink "$link")" = "$DATA_HOME/bin/bottega" ]; then
  rm -f "$link"
  echo "removed $link"
elif [ -e "$link" ] || [ -L "$link" ]; then
  echo "left $link in place: it does not point into $DATA_HOME"
fi

for item in bin templates prompts LICENSE NOTICE installed-version.json; do
  rm -rf "${DATA_HOME:?}/$item"
done
echo "removed the command and its library from $DATA_HOME"

if [ -d "$DATA_HOME/tasks" ]; then
  echo "kept your tasks in $DATA_HOME/tasks; delete them yourself when done"
fi
rmdir "$DATA_HOME" 2>/dev/null || true
echo "your configuration under ${XDG_CONFIG_HOME:-$HOME/.config}/bottega-kit was not touched"
