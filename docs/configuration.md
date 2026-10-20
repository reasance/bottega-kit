# Configuration

bottega-kit reads one personal file, an optional key file beside it, an
optional file per repository, optional prompt overrides, and a few environment
variables. No secret goes in the configuration, the prompts, the tasks or the
receipts; the key file holds what you put in it, and is read only while you
alone can read it.

## The configuration file

`${XDG_CONFIG_HOME:-~/.config}/bottega-kit/config.json`. `bottega init` writes
a starter for the harnesses it finds on PATH and refuses to overwrite an
existing file without `--force`. `bottega doctor` validates it.

```json
{
  "schema_version": 1,
  "profiles": {
    "fable":         {"harness": "claude", "model": "claude-fable-5-1", "effort": "max"},
    "opus-builder":  {"harness": "claude", "model": "claude-opus-5-5",  "effort": "high"},
    "opus-reviewer": {"harness": "claude", "model": "claude-opus-5-5",  "effort": "high"},
    "sol-builder":   {"harness": "codex",  "model": "gpt-5.6-sol",     "effort": "high"}
  },
  "roles": {"planner": "fable", "implementer": "opus-builder",
            "reviewer": "opus-reviewer", "judge": "fable"},
  "rounds": 3
}
```

| key | required | what |
|---|---|---|
| `schema_version` | yes | `1` |
| `profiles` | yes | named profiles, at least one |
| `roles` | yes | role name to profile name |
| `rounds` | no | the default round cap, a whole number of at least 1; 3 when absent |

Any other top-level key is an error.

## Profiles

A profile is a harness, a model and an effort.

| key | required | what |
|---|---|---|
| `harness` | yes | `claude` (Claude Code) or `codex` (Codex CLI) |
| `model` | yes | the model name passed to the harness |
| `effort` | yes | `claude`: `low`, `medium`, `high`, `xhigh`, `max`. `codex`: `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max` |
| `env` | no | environment variables set for the harness; values may reference your environment as `${NAME}` |
| `aliases` | no | other model names the harness may report for this model |
| `timeout` | no | seconds; the dispatch is killed after it and the task stops with `timeout` |
| `max_budget_usd` | no | `claude` only: passed as `--max-budget-usd` |

Any other key is an error.

**Model identity.** After each dispatch, the model the harness reports must be
the requested `model` or one of `aliases`. Anything else stops the task with
`identity-mismatch`. For Claude Code the check uses the session's model and
each turn's model; helper models it lists in its usage are recorded and not
checked.

**Environment references.** `"ANTHROPIC_AUTH_TOKEN": "${ZAI_API_KEY}"` is
expanded when the harness starts, from your environment or, for a name your
environment does not set, from the key file below. A referenced variable that
is set in neither fails `doctor`, `plan`, `approve`, `run` and `resume`
(exit 2); it is never sent empty. Receipts record the variable names, never
the values.

**Proxied Claude profiles.** A `claude` profile whose `env` sets
`ANTHROPIC_BASE_URL` talks to another endpoint. For it, bottega-kit:

- runs Claude Code with a fresh, temporary `CLAUDE_CONFIG_DIR`, deleted after
  the run;
- removes these variables from the inherited environment before applying the
  profile's `env`: `ANTHROPIC_API_KEY`, `CLAUDE_CODE_OAUTH_TOKEN`,
  `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_CUSTOM_HEADERS`, `ANTHROPIC_MODEL`,
  `CLAUDE_CODE_USE_BEDROCK`, `CLAUDE_CODE_USE_VERTEX`, `CLAUDE_CODE_USE_FOUNDRY`.

So your Anthropic credentials never reach the third-party endpoint. The
profile's own `env` may set any of them again.

Harnesses authenticate on their own: Claude Code through its login or
keychain, Codex through `~/.codex`. bottega-kit never handles their
credentials.

## The key file

`${XDG_CONFIG_HOME:-~/.config}/bottega-kit/secrets.env`, beside `config.json`,
holds the values profiles reference when you would rather not export them in
every shell:

```
ZAI_API_KEY=...
```

One `NAME=value` line per variable; blank lines and `#` comments are skipped,
and an `export ` prefix, quotes around the value and CRLF are tolerated. The
file is parsed, never executed. Create it with `touch` and `chmod 600`: a
file that group or others can read is refused, not read, and `doctor`,
`plan`, `approve`, `run` and `resume` say which `chmod` to run and exit 2
until you do.

The environment wins: a variable set in your environment is used even when
the file holds another value. Only the expanded profile `env` reaches a
harness, never the rest of the file, and receipts record names only. There
is no per-project `.env`: bottega-kit never reads one from a repository or a
worktree, where a key would be one `git add` away from a commit.

## Roles

| role | required |
|---|---|
| `planner` | yes |
| `implementer` | yes |
| `reviewer` | yes |
| `judge` | no; without it, the reviewer's `ready` ends the task |

A role names a profile. One profile may serve several roles. The value `auto`
is reserved and refused for now.

**Per-task overrides.** `--role implementer=sol-builder`, on `bottega new`,
changes one role for one task. The effective bindings, the configuration's
roles with the task's overrides on top, are frozen when you approve: which
profile each role uses no longer changes. The profiles themselves are read
again each time `plan`, `run` or `resume` starts, so a new model or effort in
a profile applies from the next of those commands (not mid-run), and removing
a profile a task uses makes `run` and `resume` refuse.

## bottega.json

A repository may hold `bottega.json` at its root:

```json
{"test_cmd": "make test", "base": "main"}
```

- `test_cmd` is given to the agents as the project's test command. Without it,
  they are told to find the project's documented one.
- `base` is the branch new tasks start from and pull requests target.

The base branch is chosen in this order: `bottega new --base`, then
`bottega.json`, then `origin/HEAD`, then `main`, then `master`. Nothing is
fetched, so `origin/HEAD` is as fresh as your last fetch.

## Prompts

The four prompts ship in the kit's `prompts/` directory: `planner.md`,
`implementer.md`, `reviewer.md`, `judge.md`. To change one, copy it to
`${XDG_CONFIG_HOME:-~/.config}/bottega-kit/prompts/<name>.md` and edit it; the
override wins as long as it exists.

Variables are written `{{name}}`, with no spaces. An override naming an
unknown variable is refused before anything runs; text such as
`{{ phase title }}`, with spaces, is left as it is.

| variable | value |
|---|---|
| `task_doc` | absolute path of `task.md`, the only authority |
| `task_doc_content` | `task.md` as it was when the dispatch started |
| `task_id`, `task_title` | the task's id and title |
| `worktree` | absolute path of the worktree |
| `base_branch` | the base branch |
| `signal_cmd` | absolute path of `bottega` plus `signal <absolute task directory>` (a path, so the agent's shell needs no environment variables) |
| `test_cmd` | from `bottega.json`, or empty |
| `round`, `rounds` | the current round and the cap |
| `scratch_dir` | a writable directory for this dispatch |
| `port` | a port for a dev server, `3100 + crc32(task id) % 900`, so parallel tasks differ |
| `plan_template` | the planner's part of `templates/task.md`; planner only |

## Environment variables

| variable | used by | what |
|---|---|---|
| `XDG_CONFIG_HOME` | `bottega` | the configuration and prompt overrides live under `<it>/bottega-kit` |
| `XDG_DATA_HOME` | `bottega`, `install.sh`, `uninstall.sh`, `doctor.sh` | the default data directory is `<it>/bottega-kit` |
| `BOTTEGA_DATA_HOME` | `bottega`, `install.sh`, `uninstall.sh`, `doctor.sh` | the data directory itself: the installed kit and `tasks/` |
| `BOTTEGA_BIN_HOME` | `install.sh`, `uninstall.sh` | where the `bottega` link goes; `~/.local/bin` by default |
| `BOTTEGA_INSTALL_SOURCE`, `BOTTEGA_INSTALL_REF` | `install.sh` | set by `npx bottega-kit`, recorded in `installed-version.json` |

`npx bottega-kit` passes `BOTTEGA_DATA_HOME` and `BOTTEGA_BIN_HOME` through to
`install.sh`, and takes `--ref <tag-or-branch>`, `--repo <git-url>` and
`--skip-doctor`. By default it installs the tag `bottega-kit--v<version>`
matching the npm package.

## doctor

`bottega doctor [--json]` checks python3, git and gh (a missing gh is a
warning), the configuration, the key file's mode and shape (it prints the
variable names it holds, never a value), and for each bound role: the
profile, its effort, its harness answering `--version`, and its `${NAME}`
variables, saying whether each comes from the environment or from the key
file. Any failure exits 2. `./doctor.sh`, in a clone, also compares the installed version with
the clone's.
