# bottega-kit — repository conventions

## What this is

A local CLI that runs a planner, an implementer, a reviewer and an optional
judge on coding-agent CLIs (`claude`, `codex`, `kimi`, `grok`, `muse`, `agy`)
in a git worktree. It is an
independent product: it does not import from or call delegation-kit at
runtime. The work plan and its closed decisions are recorded in `NOTES.md`.

## Layout

- `bin/bottega` — the entry point; thin. All logic is in `bin/lib/bottega/`.
- `bin/lib/bottega/` — Python 3 standard library only: `xdg` (paths), `util`
  (errors, atomic writes, slugify, git), `config` (profiles, roles, effort
  sets, `${NAME}` expansion, the `secrets.env` key file), `taskdoc` (task.md
  sections, `[T<n>]` ids, plan hash, planner-output merge, approval checks),
  `state` (state.json, the lock, task lookup), `worktree` (create, remove,
  rail hashing), `prompts`
  (the strict `{{var}}` engine and overrides), `harness/` (`HARNESS_MATRIX`,
  the registry, the `claude.py`, `codex.py`, `kimi.py`, `grok.py`, `muse.py`
  and `agy.py` drivers and parsers), `receipts`
  (run directories, `run.json`, `error.json`), `dispatch` (one role dispatch
  end to end), `loop` (the transition table `run` and `resume` drive), `cli`
  (argparse), `commands/` (one module per subcommand; `pr` drives git and gh,
  no agent).
- `prompts/<role>.md` — the planner, implementer, reviewer and judge prompts.
- `templates/task.md` — the task document template.
- `tests/<suite>.sh` runs `tests/<suite>.py` (unittest) in an isolated
  HOME/XDG/PATH set up by `tests/lib/sandbox.sh`. `tests/helpers.py` holds the
  shared fixtures. `tests/fakes/{claude,codex,kimi,grok,muse,agy}` stand in
  for the real CLIs, on the engine in `tests/fakes/fakelib.py`;
  `tests/fake-gh/gh` stands in for gh and is put on PATH only by the `pr`
  suite. `tests/version-consistency.sh` and `tests/version-tag.sh` are suites
  of their own.
- `bin/npm-installer.mjs` — the `npx bottega-kit` wrapper, plain Node 18, no
  dependencies; `tests/npm-installer.test.mjs` tests it with `node --test`
  (a CI step of its own, not a `run-tests.sh` suite).
- `docs/` — `process.md`, `configuration.md`, `compatibility.md`, `later.md`.
- Shell only for `install.sh`, `uninstall.sh`, `doctor.sh`, `run-tests.sh` and
  the `tests/*.sh` runners.
- `ruff.toml` — `target-version` py39 (the floor the README states) and
  `extend-include` for the eight Python executables without a `.py` suffix
  (`bin/bottega`, the six fakes, the fake gh), so `ruff check bin tests`
  covers them.

## The showcase site

`../bottega-kit.sh` is a repository of its own (Astro, static, on Cloudflare
Workers) generated from this checkout by its `scripts/sync-kit.mjs`: the
README, `docs/*.md`, `templates/task.md`, `prompts/*.md`, the CHANGELOG, and
the tables in `config.py`, `util.py` and `harness/__init__.py` through a
python3 import. Its home page copy, `src/data/copy.json` there, is the one
hand-written description of the kit. A change to any of those files reaches the site at the next release
sync (below). The site never runs a harness.

## Rules

- **Standard library only.** No third-party Python packages.
- **No suite dispatches a real model.** PATH in the suites holds the fakes,
  python3, git and this checkout's bottega, then `/usr/bin:/bin`.
- **Suites leave the checkout clean.** CI asserts `git status --porcelain` is
  empty after `./run-tests.sh`.
- **Exit codes:** 0 ok · 2 refused (invalid config, wrong phase, lock held,
  plan changed) · 3 stopped · 64 bad invocation. argparse errors exit 64.
- **Every harness flag lives in `HARNESS_MATRIX`** (`harness/__init__.py`);
  the suite `harness-matrix` pins each one against the work plan.
- **Receipts never hold environment values**, only variable names. The key
  file `secrets.env` is parsed, never sourced, and refused unless only its
  owner can read it; only the expanded profile `env` reaches a harness.
- **Every deviation from the work plan goes in `NOTES.md`, dated.**
- User-facing text is English, plain and short.

## Before a pull request

```sh
ruff check bin tests && ruff format --check bin tests   # ruff 0.13.0
git ls-files '*.sh' 'bin/*' 'tests/fakes/*' | while read -r f; do
  head -1 "$f" | grep -q '^#!.*\(bash\|sh\)' && printf '%s\n' "$f"
done | xargs shellcheck -S warning
bash tests/version-consistency.sh
node --test tests/npm-installer.test.mjs
./run-tests.sh
```

## Release tagging

**Never tag, push a tag, create a Release or publish to npm unless the owner
says so for that version.**

**Tag format — `bottega-kit--v<MAJOR>.<MINOR>.<PATCH>`.** Package name, two
hyphens, `v`, semver. A generic release skill defaults to a bare `v<VERSION>`;
that is wrong here.

### Before tagging

1. All four version surfaces carry the new version (below), and the
   CHANGELOG section for it is final. `[Unreleased]` stays, empty.
2. Every gate in "Before a pull request" passes, and CI is green on `main`.
3. **Refresh `docs/compatibility.md` from a real run.** One live end-to-end
   run (`new`, `plan`, `approve`, `run`, `pr`) on a throwaway repository,
   authorized by the owner, one dispatch set at a time. Replace the "Verified
   snapshot" with what was observed: date, machine, CLI versions, which
   profiles ran, what failed. Settle the open unknowns it answers, in
   `HARNESS_MATRIX` and in `NOTES.md`. Never carry numbers forward.

### Tagging and the Release

- **Tag the merge commit on `main`**, after the PR merges, never a commit on a
  feature branch.
- **Always annotated:** `git tag -a "bottega-kit--v<VERSION>" -F <notes>`.
  Subject `bottega-kit <VERSION>`, blank line, a short prose summary. Write the
  notes to a file; release prose has backticks and newlines.
- Check it locally: `tests/version-consistency.sh --tag bottega-kit--v<VERSION>`.
- **Push the commit before the tag.** A pushed tag is final: never delete and
  recreate it; fix forward with a new patch version.
- Every tag gets a GitHub Release, in the same pass, with the CHANGELOG
  section for that version as its notes:
  `gh release create "bottega-kit--v<VERSION>" --title "bottega-kit <VERSION>" --notes-file <notes>`.
- Pushing the tag runs `.github/workflows/publish-npm.yml`, which checks the
  tag against `package.json`, runs the version check with `--tag` and the npm
  wrapper test, refuses a version already on npm, and publishes through npm
  trusted publishing, with provenance and no token (the package's Trusted
  Publisher names this repository and `publish-npm.yml`). **Today that step
  fails** with `E403 OIDC permission denied`: the repository was created
  after 2026-07-15, so GitHub signs its OIDC tokens with immutable subject
  claims, which npm does not match yet (npm/cli#9969). Until npm fixes it,
  the owner publishes by hand from a clean worktree at the tag, with
  two-factor, and the release has no provenance; 0.1.0 and 0.1.1 were
  published so, see `NOTES.md`. The npm package is the wrapper only;
  `npx bottega-kit` clones the tag `bottega-kit--v<its version>`, so the tag
  must exist before anyone runs it.
- **Sync the showcase site last**, once npm serves the version: in
  `../bottega-kit.sh`, `npm run sync-kit` (it refuses a kit checkout that is
  dirty or not on the release tag), review the home page copy in
  `src/data/copy.json` against the README, `npm run build`, commit, and
  `npm run deploy` (a push to its `main` deploys instead once that repository
  is on GitHub with the Cloudflare secrets).

### Version surfaces

A bump touches **all four**; `tests/version-consistency.sh` checks them:

| file | what |
|---|---|
| `bin/lib/bottega/version.py` | `__version__` — the source of truth; `bottega --version` prints it |
| `package.json` | `.version` (the `npx bottega-kit` wrapper) |
| `README.md` | the `## Current release: X.Y.Z` heading |
| `CHANGELOG.md` | a `## [X.Y.Z] — YYYY-MM-DD` section, the newest one |

```sh
tests/version-consistency.sh
tests/version-consistency.sh --tag bottega-kit--v<VERSION>
```

CI runs shellcheck, ruff, the version check, the npm wrapper test and the
suites on every pull request and on pushes to `main`; a tag push re-runs the
version check with `--tag`. CI never runs a real model; the live run in
"Before tagging" is done by hand, only when the owner authorizes it.

### Semver

- **patch** — a bounded fix that changes no behaviour a user relies on.
- **minor** — a new command, harness or role behaviour; anything pre-1.0 that
  would otherwise be breaking.
- **major** — reserved for 1.0.

### Is this machine running the current kit?

`install.sh` writes `installed-version.json` last; `./doctor.sh` compares it
with the checkout and then runs `bottega doctor`.
