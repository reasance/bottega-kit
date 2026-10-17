#!/usr/bin/env bash
# Sourced by every tests/<suite>.sh: an isolated HOME, XDG dirs and PATH.
#
# PATH holds only the fake harnesses, python3, git and this checkout's
# bottega, then /usr/bin:/bin, so a real claude or codex can never be reached.
# The sandbox is removed on exit; nothing is written into the checkout.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON3="$(command -v python3)"
GIT="$(command -v git)"
SANDBOX="$(mktemp -d "${TMPDIR:-/tmp}/bottega-test.XXXXXX")"
trap 'rm -rf -- "$SANDBOX"' EXIT

mkdir -p "$SANDBOX/home" "$SANDBOX/config" "$SANDBOX/data" "$SANDBOX/cache" \
  "$SANDBOX/state" "$SANDBOX/bin" "$SANDBOX/tmp"
ln -s "$PYTHON3" "$SANDBOX/bin/python3"
ln -s "$GIT" "$SANDBOX/bin/git"
ln -s "$ROOT/bin/bottega" "$SANDBOX/bin/bottega"

export HOME="$SANDBOX/home"
export XDG_CONFIG_HOME="$SANDBOX/config"
export XDG_DATA_HOME="$SANDBOX/data"
export XDG_CACHE_HOME="$SANDBOX/cache"
export XDG_STATE_HOME="$SANDBOX/state"
export TMPDIR="$SANDBOX/tmp"
export PATH="$ROOT/tests/fakes:$SANDBOX/bin:/usr/bin:/bin"
export PYTHONDONTWRITEBYTECODE=1
export GIT_CONFIG_NOSYSTEM=1
export GIT_AUTHOR_NAME="bottega test" GIT_AUTHOR_EMAIL="test@example.invalid"
export GIT_COMMITTER_NAME="bottega test" GIT_COMMITTER_EMAIL="test@example.invalid"
unset BOTTEGA_DATA_HOME BOTTEGA_BIN_HOME BOTTEGA_FAKE_SCENARIO BOTTEGA_FAKE_LOG \
  BOTTEGA_FAKE_BOTTEGA ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN \
  CLAUDE_CODE_OAUTH_TOKEN OPENAI_API_KEY 2>/dev/null || true
cd "$SANDBOX" || exit 1
