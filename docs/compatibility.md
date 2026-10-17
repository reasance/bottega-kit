# Compatibility and release verification

This page records how each harness is driven and what was observed to work, on
which machine, on which day. A successful run proves that the exact harness,
model, effort and role tested ran as described; it says nothing about which
model to use, which stays your choice in the configuration.

Each release replaces the snapshot below with what was actually observed
before tagging. Numbers are never carried forward from an earlier release.

## Verified snapshot

**0.1.0: no live run has been recorded yet.** The flags below are untested
against the real `claude` and `codex` CLIs. Every suite runs against fake
executables that print the event shapes the real CLIs are expected to print.
The open unknowns are listed in `NOTES.md`, under "Live-probe unknowns", and
summarised at the end of this page.

What was checked, offline, on 2026-10-17 on macOS:

- the regression suites (`./run-tests.sh`), with fake `claude`, `codex` and
  `gh`, real git, and a local bare `origin`;
- the npm wrapper test (`node --test tests/npm-installer.test.mjs`), against a
  local `file://` clone with a matching tag;
- ShellCheck at `-S warning`, ruff, and the version check, including the tag
  rules on a tag made in a temporary copy.

The CLIs the flags were written against: Claude Code 2.1.302 and Codex CLI
0.163.0, from their `--help`; gh 2.102.0.

## The harness matrix

Every flag lives in `HARNESS_MATRIX`, in `bin/lib/bottega/harness/__init__.py`.
The `harness-matrix` suite pins each cell.

### Common to both

- The working directory is the task's worktree; the prompt goes on stdin.
- The environment is yours plus the profile's `env` (see
  [configuration.md](configuration.md) for proxied Claude profiles).
- A profile `timeout` kills the harness's process group; the task stops with
  `timeout`. After every run the process group is killed, so nothing the
  agent started outlives the dispatch.

### claude

Base command:

```
claude -p --model <model> --effort <effort> --output-format stream-json --verbose
  --permission-prompts none --setting-sources "" --strict-mcp-config
  --mcp-config '{"mcpServers":{}}' --settings '{"disableAllHooks":true}'
  --disable-slash-commands --no-session-persistence --add-dir <task dir>
  [--max-budget-usd <n>]
```

| role | added flags |
|---|---|
| planner | `--permission-mode dontAsk --tools Read,Glob,Grep` |
| implementer | `--permission-mode acceptEdits --tools Read,Edit,Write,Glob,Grep,Bash --allowedTools Bash --disallowedTools "Bash(git push *)" "Bash(gh *)"` |
| reviewer | `--permission-mode dontAsk --tools Read,Glob,Grep,Bash --allowedTools Bash --disallowedTools "Bash(git push *)" "Bash(gh *)" "Bash(git commit *)"` |
| judge | `--permission-mode dontAsk --tools Read,Glob,Grep,Bash --allowedTools "Bash(git diff *)" "Bash(git log *)" "Bash(git show *)" "Bash(<bottega> signal *)"` |

`--fallback-model` and `--bare` are never used. Read from the `stream-json`
events: the final message from the `result` event's `.result`; the model
from the `system/init` event's `.model` and each assistant event's
`.message.model`; usage, cost, duration and turns from the `result` event;
`is_error: true` is a failed dispatch.

The Claude reviewer has Bash so it can run tests. That it does not change
code is enforced by the rails (HEAD and the tracked diff checked around the
run), not by a sandbox.

### codex

Base command:

```
codex exec -m <model> -c model_reasoning_effort="<effort>" -c approval_policy="never"
  -c mcp_servers={} -c features.multi_agent=false --json -o <run dir>/output.md
  --ephemeral --color never -C <worktree> -
```

| role | added flags |
|---|---|
| planner | `--sandbox read-only` |
| implementer | `--sandbox workspace-write --add-dir <task dir>` |
| reviewer | `--sandbox workspace-write --add-dir <task dir>` |
| judge | `--sandbox workspace-write --add-dir <task dir>` |

`--ignore-user-config` is never used, because your provider and login may
live in `~/.codex/config.toml`. The final message is the `-o` file. The model
comes from the top-level `model` or `response.model` of any event, or the
model of a session or turn event; usage from the last `turn.completed`.

The Codex reviewer and judge can write in the worktree, because tests write
caches. The rails stop the task if tracked code changes.

### gh, for bottega pr

```
gh pr view <branch> --repo <host/owner/repo> --json url,state
gh pr create --repo <host/owner/repo> --base <base> --head <branch> --title <title> --body-file <file>
```

`<host/owner/repo>` comes from `origin`'s configured URL. `pr` runs
`git push -u origin <branch>` itself; `gh` never pushes.

## Open unknowns

Each needs one authorized live run to settle:

- the tool names `--tools` accepts, and whether a comma list is one argument;
- the permission-rule spelling, `Bash(git push *)` or `Bash(git push:*)`;
- whether `--permission-prompts none` with `acceptEdits` lets Edit and Write
  proceed in the worktree and in the `--add-dir` directory, and whether
  `dontAsk` with `--allowedTools Bash` lets the reviewer run tests for up to
  ten minutes;
- whether the variadic `--allowedTools` and `--disallowedTools` lists parse as
  the last options, with the prompt on stdin;
- whether the judge can run its diff and signal commands under its four rules;
- the `stream-json` field names on Claude Code 2.1.302, and which helper models
  `modelUsage` lists;
- the exact model names each CLI reports for each profile;
- Codex 0.163.0's event names, where it reports the model, and whether `-o` is
  written when the final message is empty;
- whether `codex exec` accepts `-c mcp_servers={}` and
  `-c features.multi_agent=false`;
- whether gh accepts `--repo host/owner/repo` for a GitHub Enterprise host,
  and what `gh pr view <branch>` returns for a merged pull request.

## Reproduce the offline gates

```sh
ruff check bin tests && ruff format --check bin tests
bash tests/version-consistency.sh
node --test tests/npm-installer.test.mjs
./run-tests.sh
```

The release gate (`CLAUDE.md`, "Before tagging") is one live end-to-end run, `new`, `plan`,
`approve`, `run`, `pr`, on a throwaway repository, run only when the owner
authorizes it. Its results replace the snapshot above.
