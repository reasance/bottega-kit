# bottega-kit — repository conventions

## What this is

A local CLI that runs a planner, an implementer, a reviewer and an optional
judge on coding-agent CLIs (`claude`, `codex`) in a git worktree. It is an
independent product: it does not import from or call delegation-kit at
runtime. The work plan and its closed decisions are recorded in `NOTES.md`.

## Layout

- `bin/bottega` — the entry point; thin. All logic is in `bin/lib/bottega/`.
- `bin/lib/bottega/` — Python 3 standard library only: `xdg` (paths), `util`
  (errors, atomic writes, slugify, git), `config` (profiles, roles, effort
  sets, `${NAME}` expansion), `taskdoc` (task.md sections, `[T<n>]` ids, plan
  hash, planner-output merge, approval checks), `state` (state.json, the
  lock, task lookup), `worktree` (create, remove, rail hashing), `prompts`
  (the strict `{{var}}` engine and overrides), `harness/` (`HARNESS_MATRIX`,
  the registry, `claude.py` and `codex.py` drivers and parsers), `receipts`
  (run directories, `run.json`, `error.json`), `dispatch` (one role dispatch
  end to end), `loop` (the transition table `run` and `resume` drive), `cli`
  (argparse), `commands/` (one module per subcommand).
- `prompts/<role>.md` — the planner, implementer, reviewer and judge prompts.
- `templates/task.md` — the task document template.
- `tests/<suite>.sh` runs `tests/<suite>.py` (unittest) in an isolated
  HOME/XDG/PATH set up by `tests/lib/sandbox.sh`. `tests/helpers.py` holds the
  shared fixtures. `tests/fakes/{claude,codex}` stand in for the real CLIs.
  `tests/version-consistency.sh` is a suite of its own.
- Shell only for `install.sh`, `uninstall.sh`, `doctor.sh`, `run-tests.sh` and
  the `tests/*.sh` runners.

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
- **Receipts never hold environment values**, only variable names.
- **Every deviation from the work plan goes in `NOTES.md`, dated.**
- User-facing text is English, plain and short.

## Before a pull request

```sh
ruff check bin tests && ruff format --check bin tests   # ruff 0.13.0
git ls-files '*.sh' 'bin/*' 'tests/fakes/*' | while read -r f; do
  head -1 "$f" | grep -q '^#!.*\(bash\|sh\)' && printf '%s\n' "$f"
done | xargs shellcheck -S warning
bash tests/version-consistency.sh
./run-tests.sh
```

## Release tagging

**Tag format — `bottega-kit--v<MAJOR>.<MINOR>.<PATCH>`.** Package name, two
hyphens, `v`, semver. A generic release skill defaults to a bare `v<VERSION>`;
that is wrong here.

- **Never tag unless the owner says so.**
- **Always annotated:** `git tag -a -F <notes-file>`. Subject
  `bottega-kit <VERSION>`, blank line, a short prose summary.
- **Tag the merge commit on `main`**, after the PR merges.
- **Push the commit before the tag.** A pushed tag is final.
- Every tag gets a GitHub Release:
  `gh release create "bottega-kit--v<VERSION>" --title "bottega-kit <VERSION>" --notes-file <notes>`,
  with the CHANGELOG section as the notes.

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

CI runs shellcheck, ruff, the version check and the suites on every pull
request and on pushes to `main`; a tag push re-runs the version check with
`--tag`. CI never runs a real model; the live gates in the work plan are run by
hand, only when the owner authorizes them.

### Semver

- **patch** — a bounded fix that changes no behaviour a user relies on.
- **minor** — a new command, harness or role behaviour; anything pre-1.0 that
  would otherwise be breaking.
- **major** — reserved for 1.0.

### Is this machine running the current kit?

`install.sh` writes `installed-version.json` last; `./doctor.sh` compares it
with the checkout and then runs `bottega doctor`.
