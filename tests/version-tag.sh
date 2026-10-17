#!/usr/bin/env bash
# tests/version-consistency.sh --tag, against tags made in a temporary copy.
#
# The release-tag rules (name bottega-kit--v<version>, annotated, subject
# "bottega-kit <version>") are checked on a throwaway repository built from
# this checkout's version surfaces. This repository is never tagged.
set -euo pipefail
JQ="$(command -v jq)" || { printf 'jq is required\n' >&2; exit 69; }
# shellcheck source=tests/lib/sandbox.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/sandbox.sh"
ln -s "$JQ" "$SANDBOX/bin/jq"

VERSION="$(sed -n 's/^__version__ = "\([^"]*\)"$/\1/p' "$ROOT/bin/lib/bottega/version.py")"
TAG="bottega-kit--v$VERSION"
COPY="$SANDBOX/release"
mkdir -p "$COPY/tests"
cp -R "$ROOT/bin" "$COPY/bin"
cp "$ROOT/package.json" "$ROOT/README.md" "$ROOT/CHANGELOG.md" "$COPY/"
cp "$ROOT/tests/version-consistency.sh" "$COPY/tests/"
git -C "$COPY" init -q -b main
git -C "$COPY" add -A
git -C "$COPY" commit -q -m "release $VERSION"

pass=0
check() { # expectation (pass|fail) description tag-name [grep pattern]
  local out rc=0
  out="$(bash "$COPY/tests/version-consistency.sh" --tag "$3" 2>&1)" || rc=$?
  if [ "$1" = pass ] && [ "$rc" -ne 0 ]; then
    printf 'FAIL: %s: expected a pass, got rc=%s:\n%s\n' "$2" "$rc" "$out" >&2; exit 1
  fi
  if [ "$1" = fail ] && { [ "$rc" -eq 0 ] || ! grep -q -- "$4" <<<"$out"; }; then
    printf 'FAIL: %s: expected a failure matching %s, got rc=%s:\n%s\n' \
      "$2" "$4" "$rc" "$out" >&2; exit 1
  fi
  pass=$((pass + 1))
}

git -C "$COPY" tag -a "$TAG" -m "bottega-kit $VERSION" -m "A summary of the release."
check pass "annotated tag with the right subject" "$TAG"
check fail "another version in the tag name" "bottega-kit--v9.9.9" "tag name"
check fail "a bare v tag" "v$VERSION" "tag name"

git -C "$COPY" tag -d "$TAG" >/dev/null
check fail "the tag is missing" "$TAG" "not present locally"

git -C "$COPY" tag "$TAG"
check fail "a lightweight tag" "$TAG" "tag is annotated"

git -C "$COPY" tag -d "$TAG" >/dev/null
git -C "$COPY" tag -a "$TAG" -m "release $VERSION"
check fail "the wrong subject" "$TAG" "tag message subject"

printf 'version tag: %s checks passed (%s, in a temporary copy)\n' "$pass" "$TAG"
