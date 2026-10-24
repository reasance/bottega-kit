# Configuration

bottega-kit reads one personal file, an optional key file beside it, an
optional file per repository, optional prompt overrides, and a few environment
variables. No secret goes in the configuration, the prompts, the tasks or the
receipts; the key file holds what you put in it, and is read only while you
alone can read it.

## The configuration file

`${XDG_CONFIG_HOME:-~/.config}/bottega-kit/config.json`. `bottega init` writes
a starter for the harnesses it finds on PATH and refuses to overwrite an
existing file without `--force`. `bottega doctor` validates it. Below is the
starter with both `claude` and `codex` on PATH; with `claude` alone it has
no `sol-builder`; with `codex` alone it has only `sol-builder`, bound as
planner, implementer and reviewer, and no judge. With `kimi` on PATH it also
has a `kimi` profile (`"harness": "kimi", "model": "kimi-code/k3.1-pro",
"effort": "high"`), bound the same way as `sol-builder` when `kimi` is the
only CLI found, to no role otherwise. `grok` and `muse` on PATH add a
`grok` profile (`"harness": "grok", "model": "grok-4.7", "effort": "high"`)
and a `muse` profile (`"harness": "muse", "model": "muse-wonder-1.0",
"effort": "high"`) the same way, and `agy` a `gemini` profile (`"harness":
"agy", "model": "gemini-3.8-flash-high", "effort": "high"`); the first CLI
found in the order `claude`, `codex`, `kimi`, `grok`, `muse`, `agy` binds
the roles. With none of them, it is the
`claude` one.

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
| `harness` | yes | `claude` (Claude Code), `codex` (Codex CLI), `kimi` (Kimi Code), `grok` (Grok Build), `muse` (Muse Code) or `agy` (Antigravity CLI) |
| `model` | yes | the model name passed to the harness; for `kimi`, a model alias of Kimi Code's `config.toml`, such as `kimi-code/k3.1-pro` |
| `effort` | yes | `claude`: `low`, `medium`, `high`, `xhigh`, `max`. `codex`: `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`. `kimi`: `low`, `high`, `max`. `grok`: `low`, `medium`, `high`, `xhigh`. `muse`: `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`, `ultra`. `agy`: `low`, `medium`, `high`, `xhigh`, `max`, as far as the model takes them |
| `env` | no | environment variables set for the harness; values may reference your environment as `${NAME}` |
| `aliases` | no | other model names the harness may report for this model |
| `timeout` | no | seconds; the dispatch is killed after it and the task stops with `timeout` |
| `max_budget_usd` | no | `claude` only: passed as `--max-budget-usd` |

Any other key is an error.

**Model identity.** After each dispatch, the model the harness reports must be
the requested `model` or one of `aliases`. Anything else stops the task with
`identity-mismatch`. For Claude Code the check uses the session's model and
each turn's model; helper models it lists in its usage are recorded and not
checked; Grok Build is read the same way. Muse Code names each model that
served the run, and every one is checked. Codex and Kimi Code report no
model, nor does the Antigravity CLI, so nothing is checked: their receipts
say `model_identity_source: requested-only`, and `aliases` has no effect on
a `codex`, `kimi` or `agy` profile. A `kimi` receipt also records, under
`usage`, the model and effort Kimi Code asked its provider for and the
tokens, read from Kimi Code's own session log; they are not a check.

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
profile's own `env` may set any of them again. Claude Code does not know the
endpoint's prices: the receipt's `cost_usd` and the `max_budget_usd` limit
use its own default table, which overstated a GLM run on Z.AI about
fifteenfold on 2026-10-20, a MiniMax run about 36 times and a Kimi run
about three times on 2026-10-23 (see [compatibility.md](compatibility.md)).

Endpoints that have run live, each with the model name it reported:

| provider | `ANTHROPIC_BASE_URL` | `model` | reported | key |
|---|---|---|---|---|
| Z.AI | `https://api.z.ai/api/anthropic` | `glm-5.3-flash` | `glm-5.3-flash` | a Z.AI API key |
| MiniMax | `https://api.minimax.io/anthropic` | `MiniMax-M3.1-Flash` | `MiniMax-M3.1-Flash` | a MiniMax API key |
| Moonshot (Kimi) | `https://api.moonshot.ai/anthropic` | `kimi-k3` | `kimi-k3` | a Kimi Platform API key, not the `kimi` CLI's login |

Set `ANTHROPIC_DEFAULT_OPUS_MODEL`, `ANTHROPIC_DEFAULT_SONNET_MODEL` and
`ANTHROPIC_DEFAULT_HAIKU_MODEL` to the same `model`, so the requests Claude
Code makes on its own also go to that model; on 2026-10-23 every MiniMax and
Kimi receipt listed that model alone. A model the endpoint does not serve
fails the dispatch: on 2026-10-23 `kimi-k3.1-pro` answered 404 on Moonshot's
endpoint, and its `GET /v1/models` listed up to `kimi-k3`.

Harnesses authenticate on their own: Claude Code through its login or
keychain, Codex through `~/.codex`, Kimi Code through `kimi login` and
`~/.kimi-code` (or `KIMI_CODE_HOME`), Grok Build through `grok login`, Muse
Code through its own sign-in, the Antigravity CLI through `agy`'s sign-in.
bottega-kit never handles their credentials.

**Kimi Code profiles.** `kimi` runs with your own Kimi Code configuration:
your login, your model aliases, your hooks and your MCP servers' processes,
as Codex runs with your `config.toml`. Per dispatch, bottega-kit narrows it:
an agent file lists the role's tools, an empty `--skills-dir` replaces your
skills, and the environment sets the effort, turns off Kimi Code's update
check and its built-in product skills, and disables `git push` to origin and
`gh` (see [compatibility.md](compatibility.md#kimi)). Each dispatch is also a
Kimi Code session in your history: `kimi -r <session_id>` reopens it, with
the `session_id` from the receipt's `usage`.

**Grok Build and Muse Code profiles.** Both run with your own
configuration and login, narrowed per dispatch by command-line flags: the
role's tools and permission rules for `grok`, Muse Code's write and shell
switches for `muse`, and for both the push and `gh` guards of `kimi` (see
[compatibility.md](compatibility.md#grok)). `grok` also turns off Claude
Code's and Cursor's configuration, which Grok Build otherwise loads; your
Grok Build plugins and hooks still run. `muse` turns contributor mode off
for every dispatch, whatever your setting, and keeps no session log; your
Muse Code skills still load.

**Antigravity CLI profiles.** `agy` reads its permission rules only from
its own settings file, so each dispatch runs with a temporary HOME whose
settings hold the role's rules and a symbolic link to your `agy` sign-in
file; nothing else of your `agy` configuration (settings, hooks, plugins,
MCP servers, skills, rules) reaches the run, and the directory is deleted
afterwards. Model names carry their effort (`gemini-3.8-flash-high`; `agy
models` lists them); `effort` is passed as `--effort` too. No dispatch
stays in your `agy` history. See
[compatibility.md](compatibility.md#agy).

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
file. Any failure exits 2. `./doctor.sh`, in a clone, also compares the
installed version with the clone's.
