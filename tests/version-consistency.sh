#!/usr/bin/env bash
# Enforce the version and tagging rules recorded in CLAUDE.md.
#
# A partial bump is the failure this catches: `bottega --version` then reports
# a version the repository does not claim, and nothing else notices.
#
# Usage:
#   tests/version-consistency.sh              check the four version surfaces
#   tests/version-consistency.sh --tag NAME   additionally validate a release tag
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
command -v jq >/dev/null 2>&1 || { printf 'jq is required\n' >&2; exit 69; }

TAG=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --tag) TAG="${2:-}"; shift 2 ;;
    -h|--help) sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) printf 'unknown argument: %s\n' "$1" >&2; exit 64 ;;
  esac
done

pass=0
fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
ok() { pass=$((pass + 1)); }
same() { # label expected actual
  [ "$2" = "$3" ] || fail "$1: expected '$2', got '$3'"
  ok
}

# version.py is the source of truth: it is what `bottega --version` prints.
VERSION="$(sed -n 's/^__version__ = "\([^"]*\)"$/\1/p' bin/lib/bottega/version.py)"
[ -n "$VERSION" ] || fail 'bin/lib/bottega/version.py carries no __version__'
printf '%s' "$VERSION" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$' \
  || fail "version '$VERSION' is not bare semver"
ok

if command -v python3 >/dev/null 2>&1; then
  same 'bottega --version' "bottega-kit $VERSION" \
    "$(PYTHONDONTWRITEBYTECODE=1 python3 bin/bottega --version)"
fi

same 'package.json version' "$VERSION" "$(jq -r '.version' package.json)"
same 'package.json bin entry' 'bottega-kit' "$(jq -r '.bin | keys[0]' package.json)"

readme="$(sed -n 's/^## Current release: \(.*\)$/\1/p' README.md | head -1)"
same 'README "Current release" heading' "$VERSION" "$readme"

grep -Eq "^## \[$(printf '%s' "$VERSION" | sed 's/\./\\./g')\] — [0-9]{4}-[0-9]{2}-[0-9]{2}\$" CHANGELOG.md \
  || fail "CHANGELOG.md has no '## [$VERSION] — YYYY-MM-DD' section"
ok

# The newest released CHANGELOG section must be the version being shipped, so a
# bump cannot silently land under an older heading. [Unreleased] is skipped.
newest="$(grep -m1 -E '^## \[[0-9]+\.[0-9]+\.[0-9]+\]' CHANGELOG.md | sed 's/^## \[\([^]]*\)\].*/\1/')"
same 'newest CHANGELOG section' "$VERSION" "$newest"

# No other surface may still advertise a previous version.
stale="$(grep -n -E '^## Current release: |"version": "' README.md package.json \
  | grep -v "$VERSION" || true)"
[ -z "$stale" ] || fail "stale version reference(s):"$'\n'"$stale"
ok

if [ -n "$TAG" ]; then
  # CLAUDE.md: bottega-kit--v<semver>, annotated, matching version.py.
  expected="bottega-kit--v$VERSION"
  same 'tag name' "$expected" "$TAG"
  # Require the tag object rather than skipping when it is absent: a silent
  # skip would leave the annotation rule unenforced exactly where it matters.
  # actions/checkout maps the commit onto refs/tags/<name> as a lightweight
  # ref, so CI fetches the real tag object before calling this.
  git rev-parse -q --verify "refs/tags/$TAG" >/dev/null \
    || fail "tag '$TAG' is not present locally; fetch the tag object first:
    git fetch --force origin \"refs/tags/$TAG:refs/tags/$TAG\""
  ok
  same 'tag is annotated' tag "$(git cat-file -t "$TAG")"
  subject="$(git tag -l --format='%(contents:subject)' "$TAG")"
  same 'tag message subject' "bottega-kit $VERSION" "$subject"
fi

printf 'version consistency: %s checks passed (version %s)\n' "$pass" "$VERSION"
